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
from app.services.anti_fraud import score_media
from app.services.rag import detect_fraud_by_rag
from app.utils.deps import get_current_user

router = APIRouter(prefix="/detect", tags=["detect"])
logger = logging.getLogger(__name__)


def _ensure_storage() -> Path:
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings.storage_path


@router.post("/text", response_model=DetectOut)
def detect_text(
    payload: DetectTextIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """文本反诈检测：基于 RAG 向量检索"""
    try:
        # 调用 RAG 服务进行检测
        result = detect_fraud_by_rag(payload.text)
        
        # 保存检测记录
        rec = DetectionRecord(
            user_id=current.id,
            kind="text",
            input_text=payload.text,
            risk_score=result["risk_score"],
            result_json=json.dumps(
                {
                    "reasons": result["reasons"],
                    "retrieved_cases": result["retrieved_cases"],
                    "method": "rag_vector_search",
                },
                ensure_ascii=False,
            ),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        logger.info("Detection completed for user %d: risk_score=%d", current.id, result["risk_score"])

        return DetectOut(
            id=rec.id,
            kind="text",
            risk_score=result["risk_score"],
            reasons=result["reasons"],
            created_at=rec.created_at,
        )

    except ValueError as e:
        logger.error("Detection error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in detect_text")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {e}",
        ) from e


@router.post("/media", response_model=DetectOut)
async def detect_media(
    media_type: str = Form(...),  # image|audio|video
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    media_type = media_type.strip().lower()
    if media_type not in {"image", "audio", "video"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_type must be image|audio|video",
        )

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

    risk, reasons = score_media(media_type, safe_name)
    rec = DetectionRecord(
        user_id=current.id,
        kind=media_type,
        file_path=str(saved_path),
        file_name=safe_name,
        content_type=file.content_type,
        risk_score=risk,
        result_json=json.dumps(
            {"reasons": reasons, "saved_name": saved_name, "bytes": size},
            ensure_ascii=False,
        ),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return DetectOut(
        id=rec.id,
        kind=media_type,  # type: ignore[arg-type]
        risk_score=risk,
        reasons=reasons,
        created_at=rec.created_at,
    )


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
