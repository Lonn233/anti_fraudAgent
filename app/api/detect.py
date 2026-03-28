from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import DetectionRecord, User
from app.db.session import get_db
from app.schemas import DetectOut, DetectTextIn
from app.services.rag import detect_fraud_by_rag, detect_fraud_by_image_rag, detect_fraud_by_video_rag
from app.utils.deps import get_current_user

router = APIRouter(prefix="/detect", tags=["detect"])
logger = logging.getLogger(__name__)


def _ensure_storage() -> Path:
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings.storage_path


def _save_record(
    db: Session,
    user_id: int,
    kind: str,
    result: dict,
    input_text: str | None = None,
    file_path: str | None = None,
    file_name: str | None = None,
    content_type: str | None = None,
    extra: dict | None = None,
) -> DetectionRecord:
    """统一保存检测记录到数据库。"""
    result_data = {
        "reasons": result["reasons"],
        "retrieved_cases": result["retrieved_cases"],
        "method": "rag_vector_search",
    }
    if extra:
        result_data.update(extra)

    rec = DetectionRecord(
        user_id=user_id,
        kind=kind,
        input_text=input_text,
        file_path=file_path,
        file_name=file_name,
        content_type=content_type,
        risk_score=result["risk_score"],
        result_json=json.dumps(result_data, ensure_ascii=False),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/text", response_model=DetectOut)
def detect_text(
    payload: DetectTextIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """文本反诈检测：向量化 > Milvus RAG 检索 > 风险评分"""
    try:
        result = detect_fraud_by_rag(payload.text)
        rec = _save_record(
            db, current.id, "text", result,
            input_text=payload.text,
        )
        logger.info("Text detection done: user=%d risk=%d", current.id, result["risk_score"])
        return DetectOut(
            id=rec.id, kind="text",
            risk_score=result["risk_score"],
            reasons=result["reasons"],
            created_at=rec.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Text detection error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Detection failed: {e}") from e


@router.post("/media", response_model=DetectOut)
async def detect_media(
    media_type: str = Form(...),  # image | audio | video
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """媒体反诈检测：图片/视频走 RAG 检索；音频走占位评分。"""
    media_type = media_type.strip().lower()
    if media_type not in {"image", "audio", "video"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_type must be image|audio|video",
        )

    # 保存上传文件
    storage = _ensure_storage()
    safe_name = Path(file.filename or "upload").name
    ext = Path(safe_name).suffix[:16]
    uid = uuid4().hex
    saved_name = f"{media_type}_{uid}{ext}"
    saved_path = storage / saved_name

    max_bytes = settings.max_upload_mb * 1024 * 1024
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
                        detail=f"File too large (> {settings.max_upload_mb}MB)",
                    )
                f.write(chunk)
    finally:
        await file.close()

    try:
        # 图片：RAG 检索
        if media_type == "image":
            result = detect_fraud_by_image_rag(saved_path)

        # 视频：RAG 检索
        elif media_type == "video":
            result = detect_fraud_by_video_rag(saved_path)

        # 音频：暂无多模态向量支持，返回占位结果
        else:
            result = {
                "risk_score": 0,
                "reasons": ["音频检测暂不支持向量检索，请人工核查"],
                "retrieved_cases": [],
            }

        rec = _save_record(
            db, current.id, media_type, result,
            file_path=str(saved_path),
            file_name=safe_name,
            content_type=file.content_type,
            extra={"saved_name": saved_name, "bytes": size},
        )
        logger.info("Media detection done: user=%d type=%s risk=%d", current.id, media_type, result["risk_score"])
        return DetectOut(
            id=rec.id,
            kind=media_type,  # type: ignore[arg-type]
            risk_score=result["risk_score"],
            reasons=result["reasons"],
            created_at=rec.created_at,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Media detection error")
        #HTTPException是用来返回给前端用户的错误提醒
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Detection failed: {e}") from e


@router.get("/records")
def list_records(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 50,
):
    limit = max(1, min(200, limit))
    rows = (
        db.query(DetectionRecord)
        .filter(DetectionRecord.user_id == current.id)
        .order_by(DetectionRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "risk_score": r.risk_score,
            "created_at": r.created_at,
            "file_name": r.file_name,
            "content_type": r.content_type,
        }
        for r in rows
    ]
