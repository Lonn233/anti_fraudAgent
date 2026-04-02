from __future__ import annotations

import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


def generate_fraud_advice(
    user_input: str,
    retrieved_cases: list[dict],
) -> str:
    """调用豆包 LLM 生成反诈建议。

    基于检索到的相似案例，使用 LLM 为用户生成个性化的反诈建议。

    Args:
        user_input: 用户的输入文本
        retrieved_cases: 检索到的相似案例列表，每个案例包含：
            - content: 案例内容
            - fraud_type: 诈骗类型
            - fraud_amount: 诈骗金额

    Returns:
        LLM 生成的反诈建议文本
    """
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    # 构建案例信息
    cases_text = ""
    for i, case in enumerate(retrieved_cases[:3], 1):
        content = case.get("content", "")[:200]  # 截断内容
        fraud_type = case.get("fraud_type", "未知")
        fraud_amount = case.get("fraud_amount", 0)
        cases_text += f"\n案例 {i}：\n"
        cases_text += f"  诈骗类型：{fraud_type}\n"
        cases_text += f"  诈骗金额：{fraud_amount} 元\n"
        cases_text += f"  案例描述：{content}\n"

    # 构建系统提示词
    system_prompt = """你是一个专业的反诈咨询顾问。你的任务是根据提供的真实诈骗案例，为用户提供针对性的反诈建议。

重要规则：
1. 你只能基于以下提供的三个真实诈骗案例来回答用户的问题
2. 不要编造或引用案例之外的信息
3. 分析用户的情况与案例的相似之处
4. 提供具体、可行的防范建议
5. 如果用户的情况与案例不相关，请明确说明

提供的参考案例：""" + cases_text

    # 构建用户消息
    user_message = f"""用户的情况描述：
{user_input}

请根据上述案例，为用户提供反诈建议。包括：
1. 识别可能的诈骗风险
2. 与参考案例的相似之处
3. 具体的防范措施
4. 如果已经被骗，应该采取的行动
5.精简回复，回复字数不超过300"""

    # 调用豆包 API
    url = f"{settings.doubao_ark_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "doubao-seed-2-0-pro-260215",
        "thinking":{"type":"disabled"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    logger.info("Calling Doubao LLM for fraud advice")

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)

    logger.info("Doubao LLM response: status=%s", r.status_code)

    if r.status_code != 200:
        raise httpx.HTTPStatusError(
            message=f"{r.status_code} {r.text}",
            request=r.request,
            response=r,
        )

    body = r.json()
    choices = body.get("choices", [])
    if choices and len(choices) > 0:
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if content:
            return content

    raise ValueError(f"Unexpected LLM response structure: {str(body)[:300]}")
