from __future__ import annotations

from datetime import datetime
from typing import Any
import json
import re

import httpx
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import AgentChatMessage, AgentChatSession
from app.schemas import DetectOut
from app.services import detect_serve

MAX_CONTEXT_MESSAGES = 20
GUIDE_STAGE = "guide"
AWAITING_CONFIRM_STAGE = "awaiting_confirm"
VALID_STAGES = {GUIDE_STAGE, AWAITING_CONFIRM_STAGE}
VALID_MATERIAL_TYPES = {"text", "image", "video", "audio"}


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


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _normalize_stage(value: Any, fallback: str = GUIDE_STAGE) -> str:
    stage = str(value or fallback).strip().lower()
    return stage if stage in VALID_STAGES else fallback


def _normalize_material(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    mt = str(item.get("type") or "").strip().lower()
    if mt not in VALID_MATERIAL_TYPES:
        return None
    content = str(item.get("content") or "").strip()
    summary = str(item.get("summary_text") or "").strip()
    normalized = {
        "type": mt,
        "content": content or (summary if mt == "text" else ""),
        "url": str(item.get("url") or "").strip(),
        "summary_text": summary or (content if mt in {"image", "video"} else content),
        "file_name": str(item.get("file_name") or "").strip(),
    }
    return normalized


def _normalize_materials(items: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in items or []:
        row = _normalize_material(item)
        if row is not None:
            out.append(row)
    return out


def _merge_materials(current: list[dict[str, str]], incoming: list[dict[str, str]], user_message: str) -> list[dict[str, str]]:
    merged = list(current)
    text = user_message.strip()
    if text:
        merged.append({"type": "text", "content": text, "url": "", "summary_text": text, "file_name": ""})
    merged.extend(incoming)
    return merged


def _materials_to_prompt_text(materials: list[dict[str, str]]) -> str:
    if not materials:
        return "（无补充材料）"
    lines: list[str] = []
    for i, item in enumerate(materials, 1):
        if item["type"] == "text":
            text = item["content"] or item["summary_text"]
            if text:
                lines.append(f"{i}. 文本：{text}")
            continue
        label = "音频" if item["type"] == "audio" else item["type"]
        lines.append(
            f"{i}. {label}：文件名={item['file_name'] or '（无）'}；URL={item['url'] or '（无）'}；识别摘要={item['summary_text'] or '（暂无）'}"
        )
    return "\n".join(lines) if lines else "（无补充材料）"


def _build_user_message(user_message: str, materials: list[dict[str, str]]) -> str:
    text = user_message.strip() or "（用户本轮未额外输入文字）"
    return f"用户本轮文字：{text}\n补充材料：\n{_materials_to_prompt_text(materials)}"


def _stage_prompt(stage: str, candidate_content: str, candidate_materials: list[dict[str, str]]) -> str:
    materials_text = _materials_to_prompt_text(candidate_materials)
    if stage == AWAITING_CONFIRM_STAGE:
        return (
            "当前处于检测确认阶段。系统已经识别到一段候选检测内容。"
            f"候选内容：{candidate_content or '（暂无）'}。候选原材料：{materials_text}。"
            "你只需要判断：1）这是否属于反诈检测场景；2）用户是否已经明确要求立即开始检测。"
            "如果内容相关但用户未明确要求开始，请主动询问用户是否现在立即开始检测。"
        )
    return (
        "当前处于检测引导阶段。你的任务是主动询问用户是否需要反诈检测，或者引导用户描述可疑场景。"
        "可以引导用户发送聊天记录、短信、链接、通话描述、截图、视频摘要等材料。"
        f"当前候选原材料：{materials_text}。"
        "如果用户只是普通闲聊或内容与反诈检测无关，不要强行推进到检测。"
    )


def _build_system_prompt(stage: str, candidate_content: str, candidate_materials: list[dict[str, str]]) -> str:
    return (
        "你是反诈智能助手，当前处于检测模式，负责引导用户完成诈骗内容检测。"
        "你的回复必须自然、简洁，不要暴露内部流程，并严格根据当前阶段工作。"
        + _stage_prompt(stage, candidate_content, candidate_materials)
        + "你必须严格输出 JSON："
        '{"reply":"返回给用户的自然语言回复","detect_stage":"guide|awaiting_confirm","candidate_content":"基于用户文本和媒体摘要整理后的待检测文本，没有则为空字符串","is_fraud_related":true,"user_confirmed_detect":false,"should_run_detect":false}'
        "规则：1）candidate_content 必须是适合后续文本 RAG 检测的一段中文总结，应融合用户文本和图片/视频摘要，但不要编造事实。"
        "2）只有在用户明确表达立即开始检测，且已经有待检测内容时，should_run_detect 才能为 true。"
        "3）如果内容与反诈检测无关，is_fraud_related 必须为 false，detect_stage 应为 guide。"
        "4）如果已经识别到大致可用于检测的候选内容，而用户还没明确要求开始检测，detect_stage 必须为 awaiting_confirm，reply 必须主动询问是否现在立即开始检测。"
        "5）reply 必须是正常中文文本，不要解释 JSON 字段。"
    )


def _format_detect_result(result: DetectOut) -> str:
    overall = result.report_content.overall_judgment
    rag = result.report_content.rag_result
    parts = ["已完成检测。", f"风险指数：{result.risk_index:.1f}/10"]
    if overall.fraud_type_rag:
        parts.append(f"疑似类型：{overall.fraud_type_rag}")
    if overall.conclusion:
        parts.append(f"结论：{overall.conclusion}")
    if overall.prevention_measures:
        parts.append(f"防范建议：{overall.prevention_measures}")
    if overall.post_fraud_actions:
        parts.append(f"后续处置：{overall.post_fraud_actions}")
    if rag.retrieved_case:
        parts.append(f"参考案例：{rag.retrieved_case}")
    return "\n".join(parts)


def _get_or_create_session(db: Session, user_id: int, session_id: str) -> AgentChatSession:
    chat_session = db.query(AgentChatSession).filter(AgentChatSession.user_id == user_id, AgentChatSession.session_id == session_id).first()
    if chat_session:
        return chat_session
    chat_session = AgentChatSession(user_id=user_id, session_id=session_id)
    db.add(chat_session)
    db.flush()
    return chat_session


def _trim_history(db: Session, chat_session_id: int) -> None:
    all_rows = db.query(AgentChatMessage).filter(AgentChatMessage.chat_session_id == chat_session_id).order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc()).all()
    if len(all_rows) <= MAX_CONTEXT_MESSAGES:
        return
    for row in all_rows[: len(all_rows) - MAX_CONTEXT_MESSAGES]:
        db.delete(row)
    db.commit()


def detect_reply(db: Session, user_id: int, session_id: str, user_message: str, materials: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")
    chat_session = _get_or_create_session(db, user_id, session_id)
    chat_session.mode = "detect"
    current_stage = _normalize_stage(getattr(chat_session, "detect_stage", GUIDE_STAGE), GUIDE_STAGE)
    current_candidate = (getattr(chat_session, "candidate_content", "") or "").strip()
    current_materials = _normalize_materials(getattr(chat_session, "candidate_materials", []) or [])
    incoming_materials = _normalize_materials(materials)
    merged_materials = _merge_materials(current_materials, incoming_materials, user_message)

    history_rows = db.query(AgentChatMessage).filter(AgentChatMessage.chat_session_id == chat_session.id).order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc()).all()
    history_messages = [{"role": x.role, "content": x.content} for x in history_rows[-MAX_CONTEXT_MESSAGES:]]
    llm_user_message = _build_user_message(user_message, incoming_materials)
    payload: dict[str, Any] = {
        "model": settings.doubao_chat_model,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": _build_system_prompt(current_stage, current_candidate, merged_materials)},
            *history_messages,
            {"role": "user", "content": llm_user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    url = f"{settings.doubao_ark_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.doubao_api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise httpx.HTTPStatusError(message=f"{resp.status_code} {resp.text}", request=resp.request, response=resp)

    body = resp.json()
    choices = body.get("choices", [])
    if not choices:
        raise ValueError("LLM response has no choices")
    content = (choices[0].get("message", {}).get("content") or "").strip()
    if not content:
        raise ValueError("LLM response content is empty")

    parsed = _extract_json_object(content)
    reply_text = str(parsed.get("reply") or "").strip()
    if not reply_text:
        raise ValueError("LLM response reply is empty")

    is_fraud_related = _parse_bool(parsed.get("is_fraud_related"))
    user_confirmed_detect = _parse_bool(parsed.get("user_confirmed_detect"))
    llm_should_run_detect = _parse_bool(parsed.get("should_run_detect"))
    candidate_content = str(parsed.get("candidate_content") or current_candidate).strip()
    next_stage = _normalize_stage(parsed.get("detect_stage"), current_stage)
    candidate_materials = merged_materials if (candidate_content or merged_materials) else []

    if not candidate_content:
        next_stage = GUIDE_STAGE
    elif not is_fraud_related:
        next_stage = GUIDE_STAGE
        llm_should_run_detect = False
    elif next_stage == GUIDE_STAGE and not llm_should_run_detect and not user_confirmed_detect:
        next_stage = AWAITING_CONFIRM_STAGE
        if "检测" not in reply_text and "开始" not in reply_text and "立即" not in reply_text:
            reply_text = "这些信息已经可以先进行反诈检测了。如果你手头还有聊天记录、短信、截图或其他细节，也可以补充给我；如果没有，我现在就可以开始检测，是否立即开始？"

    should_run_detect = bool(candidate_content and llm_should_run_detect and user_confirmed_detect)
    detect_result: DetectOut | None = None
    if should_run_detect:
        detect_result = detect_serve.process_text_detection(db, user_id, candidate_content, source_materials=candidate_materials)
        result_text = _format_detect_result(detect_result)
        reply_text = f"{reply_text}\n\n{result_text}" if reply_text else result_text
        next_stage = GUIDE_STAGE
        candidate_content = ""
        candidate_materials = []

    now = datetime.utcnow()
    db.add(AgentChatMessage(chat_session_id=chat_session.id, role="user", content=llm_user_message))
    db.add(AgentChatMessage(chat_session_id=chat_session.id, role="assistant", content=reply_text))
    chat_session.mode = "detect"
    chat_session.detect_stage = next_stage
    chat_session.candidate_content = candidate_content
    chat_session.candidate_materials = candidate_materials
    chat_session.updated_at = now
    db.add(chat_session)
    db.commit()
    _trim_history(db, chat_session.id)
    return {"reply": reply_text, "detect_stage": next_stage, "candidate_content": candidate_content, "candidate_materials": candidate_materials, "should_run_detect": should_run_detect, "detect_result": detect_result}
