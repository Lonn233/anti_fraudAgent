from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import AgentChatMessage, AgentChatSession, User
from app.db.session import engine, get_db
from app.schemas import (
    AgentAlertIn,
    AgentChatIn,
    AgentChatMessageOut,
    AgentChatOut,
    AgentChatSessionOut,
    AgentDetectOut,
    AgentSpeechTranscribeOut,
)
from app.services import detect_serve
from app.services.agent_chat import chat_reply
from app.services.agent_detect import detect_reply
from app.services.llm import summarize_media_for_detect, transcribe_audio_with_doubao
from app.utils.deps import get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])
_ALLOWED_DETECT_MEDIA_TYPES = {"image", "video", "audio"}
_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}


def _ensure_agent_session_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(agent_chat_sessions)")).fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if "mode" not in cols:
            conn.execute(text("ALTER TABLE agent_chat_sessions ADD COLUMN mode VARCHAR(16) DEFAULT 'chat'"))
            conn.execute(text("UPDATE agent_chat_sessions SET mode = 'chat' WHERE mode IS NULL"))
        if "detect_stage" not in cols:
            conn.execute(text("ALTER TABLE agent_chat_sessions ADD COLUMN detect_stage VARCHAR(32) DEFAULT 'guide'"))
            conn.execute(text("UPDATE agent_chat_sessions SET detect_stage = 'guide' WHERE detect_stage IS NULL"))
        if "candidate_content" not in cols:
            conn.execute(text("ALTER TABLE agent_chat_sessions ADD COLUMN candidate_content TEXT DEFAULT ''"))
            conn.execute(text("UPDATE agent_chat_sessions SET candidate_content = '' WHERE candidate_content IS NULL"))
        if "candidate_materials" not in cols:
            conn.execute(text("ALTER TABLE agent_chat_sessions ADD COLUMN candidate_materials JSON DEFAULT '[]'"))
            conn.execute(text("UPDATE agent_chat_sessions SET candidate_materials = '[]' WHERE candidate_materials IS NULL"))
        report_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(report)")).fetchall()}
        if report_cols and "source_materials" not in report_cols:
            conn.execute(text("ALTER TABLE report ADD COLUMN source_materials JSON DEFAULT '[]'"))
            conn.execute(text("UPDATE report SET source_materials = '[]' WHERE source_materials IS NULL"))


_ensure_agent_session_columns()


def _detect_media_type(file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return "image"
    if content_type.startswith("video/") or suffix in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}:
        return "video"
    if content_type.startswith("audio/") or suffix in {".mp3", ".wav", ".m4a", ".ogg", ".webm"}:
        return "audio"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="检测模式附件仅支持图片、视频或音频",
    )


def _is_audio_file(file: UploadFile) -> bool:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    return content_type.startswith("audio/") or suffix in _AUDIO_SUFFIXES


async def _save_detect_upload(file: UploadFile, media_type: str) -> tuple[Path, str, int]:
    storage = detect_serve.ensure_storage()
    type_dir = storage / media_type
    type_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    ext = Path(safe_name).suffix[:16]
    saved_name = f"{media_type}_{uuid4().hex}{ext}"
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
    return saved_path, saved_name, size


async def _build_form_materials(files: list[UploadFile]) -> list[dict[str, str]]:
    materials: list[dict[str, str]] = []
    for file in files:
        media_type = _detect_media_type(file)
        saved_path, saved_name, _size = await _save_detect_upload(file, media_type)
        relative_url = detect_serve.media_relative_path(media_type, saved_name)
        if media_type in {"image", "video"}:
            summary_text = summarize_media_for_detect(
                saved_path,
                media_kind=media_type,
                file_name=Path(file.filename or saved_name).name,
            )
        else:
            summary_text = transcribe_audio_with_doubao(
                saved_path,
                file_name=Path(file.filename or saved_name).name,
            )
        materials.append(
            {
                "type": media_type,
                "url": relative_url,
                "summary_text": summary_text,
                "file_name": Path(file.filename or saved_name).name,
            }
        )
    return materials


async def _parse_detect_request(request: Request) -> tuple[str, str, list[dict[str, str]]]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        session_id = str(form.get("session_id") or "").strip() or "default"
        user_text = str(form.get("text") or "")
        files = [item for item in form.getlist("files") if isinstance(item, UploadFile) and item.filename]
        materials = await _build_form_materials(files)
        return session_id, user_text, materials

    payload = await request.json()
    session_id = str(payload.get("session_id") or "").strip() or "default"
    user_text = str(payload.get("text") or "")
    raw_materials = payload.get("materials") or []
    if not isinstance(raw_materials, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="materials 必须为数组")
    materials: list[dict[str, str]] = []
    for item in raw_materials:
        if not isinstance(item, dict):
            continue
        materials.append(
            {
                "type": str(item.get("type") or "").strip(),
                "content": str(item.get("content") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "summary_text": str(item.get("summary_text") or "").strip(),
                "file_name": str(item.get("file_name") or "").strip(),
            }
        )
    return session_id, user_text, materials


@router.post("/chat", response_model=AgentChatOut)
def agent_chat(
    payload: AgentChatIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    try:
        result = chat_reply(
            db=db,
            user_id=current.id,
            session_id=payload.session_id,
            user_message=payload.message,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"对话失败：{err}") from err
    return AgentChatOut(
        reply=result["reply"],
        suggested_mode=result["suggested_mode"],
    )


@router.get("/chat/sessions", response_model=list[AgentChatSessionOut])
def list_chat_sessions(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = (
        db.query(AgentChatSession)
        .filter(AgentChatSession.user_id == current.id)
        .order_by(AgentChatSession.updated_at.desc(), AgentChatSession.id.desc())
        .limit(limit)
        .all()
    )
    out: list[AgentChatSessionOut] = []
    for row in rows:
        message_count = (
            db.query(AgentChatMessage)
            .filter(AgentChatMessage.chat_session_id == row.id)
            .count()
        )
        out.append(
            AgentChatSessionOut(
                session_id=row.session_id,
                updated_at=row.updated_at,
                message_count=message_count,
            )
        )
    return out


@router.get("/chat/sessions/{session_id}/messages", response_model=list[AgentChatMessageOut])
def list_chat_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
):
    chat_session = (
        db.query(AgentChatSession)
        .filter(AgentChatSession.user_id == current.id, AgentChatSession.session_id == session_id)
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    rows = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.chat_session_id == chat_session.id)
        .order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc())
        .limit(limit)
        .all()
    )
    return [AgentChatMessageOut(role=row.role, content=row.content, created_at=row.created_at) for row in rows]


@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    chat_session = (
        db.query(AgentChatSession)
        .filter(AgentChatSession.user_id == current.id, AgentChatSession.session_id == session_id)
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.chat_session_id == chat_session.id)
        .delete(synchronize_session=False)
    )
    db.delete(chat_session)
    db.commit()
    return {"ok": True}


@router.post("/detect", response_model=AgentDetectOut)
async def agent_detect(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    detect_session_id, user_text, materials = await _parse_detect_request(request)
    if not user_text.strip() and not materials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文本和附件不能同时为空")
    try:
        result = detect_reply(
            db=db,
            user_id=current.id,
            session_id=detect_session_id,
            user_message=user_text,
            materials=materials,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检测对话失败：{err}") from err
    return AgentDetectOut(
        reply=result["reply"],
        detect_stage=result["detect_stage"],
        candidate_content=result["candidate_content"],
        candidate_materials=result["candidate_materials"],
        should_run_detect=result["should_run_detect"],
        detect_result=result["detect_result"],
    )


@router.post("/alert")
def agent_alert(
    payload: AgentAlertIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ = (payload, db, current)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="预警模式接口暂未实现")


@router.post("/speech/transcribe", response_model=AgentSpeechTranscribeOut)
async def agent_speech_transcribe(
    file: UploadFile = File(...),
    session_id: str = Form(default="default"),
    mode: str = Form(default="chat"),
    current: User = Depends(get_current_user),
):
    _ = (session_id, mode, current)
    if not _is_audio_file(file):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持音频文件")
    saved_path, saved_name, _size = await _save_detect_upload(file, "audio")
    relative_url = detect_serve.media_relative_path("audio", saved_name)
    public_url = detect_serve.media_absolute_url(relative_url)
    try:
        text = transcribe_audio_with_doubao(
            public_url,
            file_name=Path(file.filename or "").name,
            audio_path=saved_path,
        )
    except httpx.HTTPStatusError as err:
        if err.response is not None and err.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="语音识别服务端点不可用（404）。请检查 DOUBAO_ASR_SUBMIT_URL / DOUBAO_ASR_RESOURCE_ID / DOUBAO_ASR_API_KEY 配置。",
            ) from err
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"语音识别服务请求失败：{err}",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音识别失败：{err}",
        ) from err
    return AgentSpeechTranscribeOut(text=text)
