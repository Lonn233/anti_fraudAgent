from __future__ import annotations

from datetime import datetime
from typing import Any
import json
import re

import httpx
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import AgentChatMessage, AgentChatSession

MAX_CONTEXT_MESSAGES = 20


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("LLM response does not contain valid JSON object")
    return json.loads(match.group(0))


def chat_reply(db: Session, user_id: int, session_id: str, user_message: str) -> dict[str, str]:
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    chat_session = (
        db.query(AgentChatSession)
        .filter(AgentChatSession.user_id == user_id, AgentChatSession.session_id == session_id)
        .first()
    )
    if not chat_session:
        chat_session = AgentChatSession(user_id=user_id, session_id=session_id)
        db.add(chat_session)
        db.flush()

    history_rows = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.chat_session_id == chat_session.id)
        .order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc())
        .all()
    )
    history_rows = history_rows[-MAX_CONTEXT_MESSAGES:]

    system_prompt = (
        "你是反诈智能助手，当前处于对话模式。"
        "请基于用户输入进行风险提示与建议，回答尽量简洁准确。"
        "当用户明显表达想进行“检测/分析诈骗内容”时，建议切换到 detect 模式。"
        "当用户明显表达想进行“预警通知/联动提醒”时，建议切换到 alert 模式。"
        "你必须严格输出 JSON："
        '{"reply":"简洁回复","suggested_mode":"none|detect|alert"}。'
        "如果无法判断或不需要切换，suggested_mode 必须是 none。"
    )
    history_messages = [{"role": x.role, "content": x.content} for x in history_rows]
    payload: dict[str, Any] = {
        "model": settings.doubao_chat_model,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": system_prompt},
            *history_messages,
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    url = f"{settings.doubao_ark_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise httpx.HTTPStatusError(
            message=f"{resp.status_code} {resp.text}",
            request=resp.request,
            response=resp,
        )

    body = resp.json()
    choices = body.get("choices", [])
    if not choices:
        raise ValueError("LLM response has no choices")
    message = choices[0].get("message", {})
    content = (message.get("content") or "").strip()
    if not content:
        raise ValueError("LLM response content is empty")
    parsed = _extract_json_object(content)
    reply_text = str(parsed.get("reply") or "").strip()
    if not reply_text:
        raise ValueError("LLM response reply is empty")
    suggested_mode = str(parsed.get("suggested_mode") or "none").strip().lower()
    if suggested_mode not in {"none", "detect", "alert"}:
        suggested_mode = "none"

    now = datetime.utcnow()
    db.add(
        AgentChatMessage(
            chat_session_id=chat_session.id,
            role="user",
            content=user_message,
        )
    )
    db.add(
        AgentChatMessage(
            chat_session_id=chat_session.id,
            role="assistant",
            content=reply_text,
        )
    )
    chat_session.updated_at = now
    db.add(chat_session)
    db.commit()

    # Keep only recent short-term context in DB for this session.
    all_rows = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.chat_session_id == chat_session.id)
        .order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc())
        .all()
    )
    if len(all_rows) > MAX_CONTEXT_MESSAGES:
        drop_rows = all_rows[: len(all_rows) - MAX_CONTEXT_MESSAGES]
        for row in drop_rows:
            db.delete(row)
        db.commit()

    return {"reply": reply_text, "suggested_mode": suggested_mode}
