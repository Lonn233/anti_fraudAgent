from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import User
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
            detail=f"Detection failed: {e}",
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
            detail="media_type must be image|audio|video",
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
                        detail=f"File too large (> {settings.max_upload_mb}MB)",
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
            detail=f"Detection failed: {e}",
        ) from e


@router.get("/records")
def list_records(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 50,
):
    return detect_serve.list_user_detection_records(db, current.id, limit)
