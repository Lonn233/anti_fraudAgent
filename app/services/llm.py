from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

_MediaKind = Literal["image", "video"]

_IMAGE_SUFFIX_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}
_VIDEO_SUFFIX_MIME: dict[str, str] = {
    ".mp4": "video/mp4",
    ".avi": "video/avi",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".flv": "video/x-flv",
}


def _data_uri_for_media_file(path: Path, media_kind: _MediaKind) -> str:
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if media_kind == "image":
        mime = _IMAGE_SUFFIX_MIME.get(suffix, "image/jpeg")
    else:
        mime = _VIDEO_SUFFIX_MIME.get(suffix, "video/mp4")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _user_content_parts(
    user_message: str,
    *,
    media_path: Path | None,
    media_kind: _MediaKind | None,
) -> str | list[dict[str, Any]]:
    if not media_path or not media_kind:
        return user_message
    if not media_path.exists():
        logger.warning("Media file not found, omitting from LLM user message: %s", media_path)
        return user_message
    data_uri = _data_uri_for_media_file(media_path, media_kind)
    if media_kind == "image":
        media_part: dict[str, Any] = {
            "type": "image_url",
            "image_url": {"url": data_uri},
        }
    else:
        media_part = {
            "type": "video_url",
            "video_url": {"url": data_uri},
        }
    return [
        {"type": "text", "text": user_message},
        media_part,
    ]


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


def generate_fraud_advice(
    user_input: str,
    retrieved_cases: list[dict],
    *,
    media_path: str | Path | None = None,
    media_kind: _MediaKind | None = None,
) -> dict[str, Any]:
    """调用豆包 LLM 生成结构化反诈建议。

    当 ``media_path`` 与 ``media_kind``（image/video）同时提供且文件存在时，用户消息为
    OpenAI 兼容的 ``content`` 数组：一段文本 + 一段带 data URI 的 base64 媒体；文件不存在则仅发送文本。
    """
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    cases_text = ""
    for i, case in enumerate(retrieved_cases[:3], 1):
        cases_text += f"\n案例 {i}：\n"
        cases_text += f"  doc_id：{case.get('doc_id', '')}\n"
        cases_text += f"  诈骗类型：{case.get('fraud_type', '未知')}\n"
        cases_text += f"  诈骗金额：{case.get('fraud_amount', 0)}\n"
        cases_text += f"  相似度：{case.get('similarity', 0)}\n"
        cases_text += f"  年龄：{case.get('age', '')}\n"
        cases_text += f"  职业：{case.get('job', '')}\n"
        cases_text += f"  地区：{case.get('region', '')}\n"
        cases_text += f"  案例内容：{case.get('content', '')}\n"

    system_prompt = """你是一个专业的反诈咨询顾问。你的任务是根据提供的真实诈骗案例，为用户提供针对性的反诈建议。
####################################
重要规则：
1. 你只能基于以下提供的三个真实诈骗案例来回答用户的问题
2. 不要编造或引用案例之外的信息
3. 分析用户的情况与案例的相似之处
4. 提供具体、可行的防范建议
5. 如果用户的情况与案例不相关，请明确说明
提供的参考案例：""" + cases_text

    user_message = f"""用户的情况描述：
{user_input}
####################################
请根据上述案例，为用户提供反诈建议。包括：
1. 识别可能的诈骗风险
2. 与参考案例的相似之处
3. 具体的防范措施
4. 如果已经被骗，应该采取的行动

####################################
你必须严格生成以下json格式：
{{
  "overall_judgment":{{
    "conclusion":"",
    "fraud_type_rag":"",
    "prevention_measures":"",
    "post_fraud_actions":""
  }},
  "rag_result":{{
    "retrieved_case":"",
    "retrival_reason":""
  }},
  "personal_info_analysis":{{
    "conclusion":""
  }}
}}"""

    url = f"{settings.doubao_ark_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    path_obj = Path(media_path) if media_path else None
    user_content = _user_content_parts(
        user_message,
        media_path=path_obj,
        media_kind=media_kind,
    )

    payload: dict[str, Any] = {
        "model": settings.doubao_chat_model,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    logger.info("Calling Doubao LLM for structured fraud advice")
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
    if not choices:
        raise ValueError(f"Unexpected LLM response structure: {str(body)[:300]}")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        raise ValueError(f"Empty LLM response content: {str(body)[:300]}")

    return _extract_json_object(content)
