from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config.settings import settings
from app.models.multimodal_detect import service as multimodal_service
from app.schemas import ModelDetectOut

router = APIRouter(prefix="/model_detect", tags=["model_detect"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=ModelDetectOut)
async def run_model_detect(
    media_type: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    """统一测试深度学习多模态检测。

    - text: media_type=text, 通过 text 传入
    - image/audio/video: 通过 file 上传
    """
    mt = media_type.strip().lower()
    if mt not in {"text", "image", "audio", "video"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="媒体类型参数错误，必须为 text|image|audio|video",
        )

    if mt == "text":
        if not (text or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当媒体类型为 text 时，text 为必填",
            )
        try:
            return multimodal_service.detect("text", text=text)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当媒体类型为 image|audio|video 时，file 为必填",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    storage = settings.storage_path / "model_detect_tmp" / mt
    storage.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    ext = Path(safe_name).suffix[:16]
    saved_name = f"{mt}_{uuid4().hex}{ext}"
    saved_path = storage / saved_name

    size = 0
    try:
        with saved_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件过大（超过 {settings.max_upload_mb}MB）",
                    )
                f.write(chunk)
    finally:
        await file.close()

    try:
        return multimodal_service.detect(mt, text=text, media_path=saved_path)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("model_detect failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"模型检测失败：{e}",
        ) from e
