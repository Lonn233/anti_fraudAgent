from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import Detect, DetectionReport, User
from app.db.session import get_db
from app.schemas import DetectOut, DetectTextIn
from app.services import detect_serve
from app.utils.deps import get_current_user

router = APIRouter(prefix="/detect", tags=["detect"])
logger = logging.getLogger(__name__)


@router.post("/text", response_model=DetectOut)
def detect_text(
    payload: DetectTextIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    try:
        return detect_serve.process_text_detection(db, current.id, payload.text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Text detection error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检测失败：{e11111}",
        ) from e


@router.post("/media", response_model=DetectOut)
async def detect_media(
    media_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    media_type = media_type.strip().lower()
    if media_type not in {"image", "audio", "video"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="媒体类型参数错误，必须为 image|audio|video",
        )

    storage = detect_serve.ensure_storage()
    type_dir = storage / media_type
    type_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    ext = Path(safe_name).suffix[:16]
    uid = uuid4().hex
    saved_name = f"{media_type}_{uid}{ext}"
    saved_path = type_dir / saved_name

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
                        detail=f"文件过大（超过 {settings.max_upload_mb}MB）",
                    )
                f.write(chunk)
    finally:
        await file.close()

    try:
        return detect_serve.process_saved_media_detection(
            db,
            current.id,
            media_type,
            saved_path,
            safe_name,
            saved_name,
            size,
            file.content_type,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Media detection error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检测失败：{e}",
        ) from e


@router.get("/records")
def list_records(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 50,
):
    return detect_serve.list_user_detection_records(db, current.id, limit)


@router.get("/reports/{detect_id}")
def get_report_by_detect_id(
    detect_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    detect_row = (
        db.query(Detect)
        .filter(Detect.id == detect_id, Detect.user_id == current.id)
        .first()
    )
    if not detect_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检测记录不存在")

    report = db.query(DetectionReport).filter(DetectionReport.id == detect_row.report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")

    return {
        "detect_id": detect_row.id,
        "report_id": report.id,
        "detect_time": detect_row.detect_time,
        "risk_index": detect_row.risk_index,
        "detect_type": detect_row.detect_type,
        "detect_content": detect_row.detect_content,
        "fraud_type": report.fraud_type,
        "overall_judgment": report.overall_judgment,
        "rag_result": report.rag_result,
        "multimodal_fusion_recognition": report.multimodal_fusion_recognition,
        "personal_info_analysis": report.personal_info_analysis,
        "created_at": report.created_at,
    }
