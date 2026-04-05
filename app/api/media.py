from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.config.settings import settings

router = APIRouter(tags=["media"])
logger = logging.getLogger(__name__)

_ALLOWED_MEDIA_TYPES = frozenset({"image", "audio", "video"})
_SAFE_FILENAME = re.compile(r"^[\w][\w.\-]*$")


def _resolve_stored_file(media_type: str, file_name: str) -> Path:
    if media_type not in _ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    if not _SAFE_FILENAME.fullmatch(file_name) or ".." in file_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    base = settings.storage_path.resolve()
    path = (base / media_type / file_name).resolve()
    try:
        path.relative_to(base / media_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        ) from None
    return path


@router.get("/media/{media_type}/{file_name}")
def get_media_file(media_type: str, file_name: str):
    """按类型子目录返回已存储的媒体文件（不做用户归属校验）。"""
    media_type = media_type.strip().lower()
    path = _resolve_stored_file(media_type, file_name)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    mime, _ = mimetypes.guess_type(path.name)
    return FileResponse(
        path,
        media_type=mime or "application/octet-stream",
        filename=path.name,
    )
