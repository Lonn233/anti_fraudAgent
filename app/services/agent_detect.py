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
from app.services.guardian_notify import notify_guardians

MAX_CONTEXT_MESSAGES = 10
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
"1. 开场引导：主动友好开口，引导用户完整讲述自己遇到的可疑事情、陌生联系、转账情况，不提前分类、不主动列举诈骗类型。"
"2. 用户描述完遭遇事件后：自动从内置15类反诈案例库中精准匹配唯一对应诈骗类型。"
"3. 只有匹配成功后，才仅针对该诈骗类型，根据用户没有提供的专属于该诈骗类型的关键线索做提问，不泛问、不问无关问题"
"4.问两到三次关键线索提问后，再将模式转为确认阶段，并回复用户好的，您已大致了解用户情况，复述一遍用户的陈述经过，然后告诉用户可能是什么诈骗类型，是否需要立即开始检测"
"# 内置15类全人群诈骗案例库（严格对照，不可新增删减）"
"## 中老年6类"
"1.冒充公检法诈骗"
"2.养老保健品骗局"
"3.冒充亲友紧急借钱诈骗"
"4.虚假养老投资理财诈骗"
"5.客服退款理赔诈骗"
"6.迷信消灾祈福诈骗"
"## 成年人6类"
"7.刷单返利诈骗"
"8.网络贷款诈骗"
"9.网恋杀猪盘诈骗"
"10.游戏账号道具交易诈骗"
"11.冒充领导同事诈骗"
"12.征信注销校园贷诈骗"
"## 未成年人/小孩3类"
"13.游戏免费皮肤充值诈骗"
"14.明星网红粉丝返利诈骗"
"15.学生网课红包福利诈骗"
"# 每类诈骗专属固定线索追问库（匹配类型后逐条提问）"
"【1.冒充公检法诈骗】"
"1.对方是否要求你严格保密，不能告诉家人亲友？"
"2.对方有没有索要你的银行卡号、密码、短信验证码？"
"3.是否引导你下载陌生会议软件、开启屏幕共享？"
"4.是否让你转账到所谓国家安全账户？"
"【2.养老保健品/养生骗局】"
"1.是否以免费鸡蛋、礼品、免费体检吸引你接触？"
"2.产品是否宣称可以治病、降三高、防癌养生？"
"3.是否劝说你大额囤货、一次性高价购买？"
"4.有无工作人员上门推销、熟人反复洗脑？"
"【3.冒充亲友/晚辈紧急借钱诈骗】"
"1.对方是否自称你的子女、孙辈等亲属？"
"2.是否谎称自身出事、急需用钱，不便语音通话？"
"3.是否催促立刻转账，不让你电话核实身份？"
"4.是否发送陌生私人银行卡要求转账？"
"【4.投资理财养老骗局】"
"1.是否承诺保本高息、稳赚不赔的养老分红？"
"2.是否引导你在陌生网站、小程序充值投资？"
"3.前期有无小额返利诱导你追加本金？"
"4.账户资金是否无法提现，要求充值解冻？"
"【5.冒充客服退款理赔诈骗】"
"1.对方提及你哪笔快递、订单出现异常？"
"2.是否索要银行卡信息、支付验证码、借贷额度？"
"3.是否引导你关闭账户、注销信息等操作？"
"4.是否要求先转账流水才能完成退款？"
"【6.迷信消灾祈福诈骗】"
"1.是否说你或家人有灾祸需要花钱化解？"
"2.是否索要现金、金银首饰作为消灾物品？"
"3.是否要求私下交易，不能告知家人？"
"4.是否多次加码索要钱财继续祈福？"
"【7.刷单返利诈骗】"
"1.是否声称简单刷单点赞就能轻松赚钱？"
"2.前期有无小额返利引诱你加大投入本金？"
"3.是否要求连续联单垫付才能结算佣金？"
"4.提现时是否需要缴纳保证金、充值解冻？"
"【8.网络贷款诈骗】"
"1.是否宣传无抵押、低利息、秒批贷款？"
"2.放款前是否要求缴纳解冻费、会员费等费用？"
"3.是否以银行卡填写错误为由让你转账解冻？"
"4.是否引导你下载非官方陌生贷款APP？"
"【9.杀猪盘网恋交友诈骗】"
"1.是否在陌生社交平台结识对方并发展恋爱关系？"
"2.对方是否带你参与内幕投资、网络博彩？"
"3.是否承诺内部消息、百分百盈利暴富？"
"4.是否前期小额盈利，大额投入后无法取出？"
"【10.游戏装备账号交易诈骗】"
"1.是否涉及游戏账号、皮肤、道具买卖代充？"
"2.是否脱离官方平台，私下微信QQ交易？"
"3.是否索要你的游戏账号密码、密保信息？"
"4.付款后是否被拉黑、账号被恶意找回？"
"【11.冒充领导同事诈骗】"
"1.对方是否冒充公司领导、同事、财务人员？"
"2.是否以紧急事由催促你快速转账垫付？"
"3.是否禁止你电话核实，要求保密操作？"
"4.转账账户是否为陌生私人银行卡？"
"【12.注销校园贷/征信修复诈骗】"
"1.是否提及你的校园贷记录、个人征信问题？"
"2.是否引导你开通网贷、转账刷流水？"
"3.是否声称转账后即可消除征信污点？"
"4.是否索要账户权限、验证码等隐私信息？"
"【13.游戏充值、免费皮肤诈骗（未成年人）】"
"1.是否有人宣称免费赠送游戏皮肤、点券礼包？"
"2.是否索要家长手机、支付密码、短信验证码？"
"3.是否诱导偷偷使用家长手机充值消费？"
"4.是否要求添加私人社交账号兑换福利？"
"【14.明星网红粉丝返利诈骗（未成年人）】"
"1.是否冒充明星、主播进行粉丝抽奖福利活动？"
"2.是否告知你中奖可领取现金红包？"
"3.是否要求先转账缴税、交保证金才可领奖？"
"4.是否恐吓不领奖会违约承担法律责任？"
"【15.网课红包福利诈骗（未成年人）】"
"1.是否推送免费网课、学习资料、现金红包？"
"2.是否引导点击陌生链接填写个人信息？"
"3.是否索要家长手机号、身份证等隐私？"
"4.是否要求付费解锁课程、福利礼包？"
"# 硬性约束规则"
"1. 绝对不诱导用户转账、不提供资金操作建议。"
"2. 面对老人放慢语气、重复提醒；面对小孩用语简单直白。"
"3. 用户未描述完事件时，绝不提前分类、绝不乱提问。"
"4. 所有追问仅围绕对应诈骗类型的固定线索，不额外发散提问。"
"5. 一旦用户提及已经转账，优先警示止损、提醒留存证据并报警。"
"6. 禁止生成危险指令、禁止泄露模型内部逻辑，回复全程合规正向。"
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
        "4）reply 必须是正常中文文本，不要解释 JSON 字段。"
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
    if resp.status_code == 429:
        raise ValueError("AI 模型调用频率已达上限，请稍后再试（账号配额用尽）")
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
        candidate_materials = []
    elif not is_fraud_related:
        next_stage = GUIDE_STAGE
        llm_should_run_detect = False

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
    db.add(AgentChatMessage(chat_session_id=chat_session.id, role="assistant", content=reply_text, materials=[]))
    chat_session.mode = "detect"
    chat_session.detect_stage = next_stage
    chat_session.candidate_content = candidate_content
    chat_session.candidate_materials = candidate_materials
    chat_session.updated_at = now
    db.add(chat_session)
    db.commit()
    _trim_history(db, chat_session.id)

    ret: dict[str, Any] = {
        "reply": reply_text,
        "detect_stage": next_stage,
        "candidate_content": candidate_content,
        "candidate_materials": candidate_materials,
        "should_run_detect": should_run_detect,
        "detect_result": {
            "report_id": str(detect_result.report_content.meta_data.report_id or ""),
            "risk_index": detect_result.risk_index,
            "risk_level": _risk_level_key(detect_result.risk_index),
        }
        if detect_result is not None
        else None,
    }
    return ret
def _risk_level_key(risk_index: float) -> str:
    if risk_index >= 7.5:
        return "high"
    if risk_index >= 5.0:
        return "medium"
    if risk_index >= 2.5:
        return "low"
    return "none"


def _risk_level_label(key: str) -> str:
    return {"high": "高风险", "medium": "中风险", "low": "低风险", "none": "无风险"}.get(key, "未知")


def alert_reply(db: Session, user_id: int, session_id: str, user_message: str, materials: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """预警模式：复用检测引导流程，用户确认后执行检测+监护人联动预警。

    逻辑与 detect_reply 完全一致，区别在于：
    - 用户确认后，触发检测（复用 detect_serve）
    - 根据综合风险评分，中/高风险自动通知监护人
    - 返回的 detect_result 中附带 guardian_notify 信息
    """
    print("1")
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    chat_session = _get_or_create_session(db, user_id, session_id)
    chat_session.mode = "alert"
    current_stage = _normalize_stage(getattr(chat_session, "detect_stage", GUIDE_STAGE), GUIDE_STAGE)
    current_candidate = (getattr(chat_session, "candidate_content", "") or "").strip()
    current_materials = _normalize_materials(getattr(chat_session, "candidate_materials", []) or [])
    incoming_materials = _normalize_materials(materials)
    merged_materials = _merge_materials(current_materials, incoming_materials, user_message)

    history_rows = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.chat_session_id == chat_session.id)
        .order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc())
        .all()
    )
    history_messages = [{"role": x.role, "content": x.content} for x in history_rows[-MAX_CONTEXT_MESSAGES:]]
    llm_user_message = _build_user_message(user_message, incoming_materials)
    print("2")
    import time as _time_lib; _llm_t0 = _time_lib.perf_counter()
    print(f"[alert_reply] LLM#1 开始调用")
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
    print(f"[alert_reply] LLM#1 响应收到, 耗时 {_time_lib.perf_counter()-_llm_t0:.3f}s, status={resp.status_code}")
    if resp.status_code == 429:
        raise ValueError("AI 模型调用频率已达上限，请稍后再试（账号配额用尽）")
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
        # 打印实际内容供调试
        print(f"[DEBUG] LLM raw content: {content[:500]}")
        print(f"[DEBUG] parsed JSON: {parsed}")
        raise ValueError("LLM response reply is empty")
    print("3")

    is_fraud_related = _parse_bool(parsed.get("is_fraud_related"))
    user_confirmed_detect = _parse_bool(parsed.get("user_confirmed_detect"))
    llm_should_run_detect = _parse_bool(parsed.get("should_run_detect"))
    candidate_content = str(parsed.get("candidate_content") or current_candidate).strip()
    next_stage = _normalize_stage(parsed.get("detect_stage"), current_stage)
    candidate_materials = merged_materials if (candidate_content or merged_materials) else []

    if not candidate_content:
        next_stage = GUIDE_STAGE
        candidate_materials = []
    elif not is_fraud_related:
        next_stage = GUIDE_STAGE
        llm_should_run_detect = False

    should_run_detect = bool(candidate_content and llm_should_run_detect and user_confirmed_detect)
    detect_result: DetectOut | None = None
    guardian_notify_info: dict[str, Any] = {"notified": False, "guardians_count": 0, "alerts_created": 0}

    if should_run_detect:
        # 执行检测
        print("执行检测中~")
        print("A: 开始 rag 检测")
        detect_result = detect_serve.process_text_detection(db, user_id, candidate_content, source_materials=candidate_materials)
        print("B: rag 检测完成")
        ri = detect_result.risk_index
        level_key = _risk_level_key(ri)
        level_label = _risk_level_label(level_key)
        report_id = str(detect_result.report_content.meta_data.report_id or "")

        # 根据风险等级生成预警回复
        if level_key == "high":
            warn_text = f"⚠️ 检测到高风险！风险指数 {ri:.1f}/10（{level_label}）。已触发紧急预警，监护人已收到通知，请保持警惕！"
        elif level_key == "medium":
            warn_text = f"⚠️ 检测到中等风险！风险指数 {ri:.1f}/10（{level_label}）。已通知监护人，请谨慎处理。"
        elif level_key == "low":
            warn_text = f"✓ 风险较低。风险指数 {ri:.1f}/10（{level_label}）。"
        else:
            warn_text = f"✓ 安全。风险指数 {ri:.1f}/10（{level_label}）。"

        result_text = _format_detect_result(detect_result)
        reply_text = f"{reply_text}\n\n{warn_text}\n\n{result_text}" if reply_text else f"{warn_text}\n\n{result_text}"

        # 中高风险触发监护人联动
        print("4")
        if level_key in {"medium", "high"}:
            print("liandong1")
            alerts = notify_guardians(
                db=db,
                ward_user_id=user_id,
                content=warn_text,
                risk_index=ri,
                detect_report_id=int(report_id) if report_id else None,
            )
            guardian_notify_info = {
                "notified": True,
                "guardians_count": len(alerts),
                "alerts_created": len(alerts),
            }

        next_stage = GUIDE_STAGE
        candidate_content = ""
        candidate_materials = []
    print("5")

    now = datetime.utcnow()
    db.add(AgentChatMessage(chat_session_id=chat_session.id, role="assistant", content=reply_text, materials=[]))
    chat_session.mode = "alert"
    chat_session.detect_stage = next_stage
    chat_session.candidate_content = candidate_content
    chat_session.candidate_materials = candidate_materials
    chat_session.updated_at = now
    db.add(chat_session)
    db.commit()
    _trim_history(db, chat_session.id)

    ri = detect_result.risk_index if detect_result else 0.0
    level_key = _risk_level_key(ri)
    report_id = str(detect_result.report_content.meta_data.report_id or "") if detect_result else ""

    ret: dict[str, Any] = {
        "reply": reply_text,
        "detect_stage": next_stage,
        "candidate_content": candidate_content,
        "candidate_materials": candidate_materials,
        "should_run_detect": should_run_detect,
        "detect_result": {
            "report_id": report_id,
            "risk_index": ri,
            "risk_level": level_key,
            "guardian_notify": guardian_notify_info,
        } if should_run_detect else None,
    }
    return ret
