from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import AgentChatMessage, AgentChatSession, User
from app.db.session import get_db
from app.schemas import (
    AgentAlertIn,
    AgentChatIn,
    AgentChatMessageOut,
    AgentChatOut,
    AgentChatSessionOut,
    AgentDetectIn,
)
from app.services.agent_chat import chat_reply
from app.utils.deps import get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])


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
    return AgentChatOut(reply=result["reply"], suggested_mode=result["suggested_mode"])


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


@router.post("/detect")
def agent_detect(
    payload: AgentDetectIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ = (payload, db, current)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="检测模式接口暂未实现")


@router.post("/alert")
def agent_alert(
    payload: AgentAlertIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ = (payload, db, current)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="预警模式接口暂未实现")
