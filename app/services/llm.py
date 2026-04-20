from __future__ import annotations

import base64
import json
import logging
import re
import uuid
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
_AUDIO_SUFFIX_MIME: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
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


def summarize_media_for_detect(
    media_path: str | Path,
    *,
    media_kind: _MediaKind,
    file_name: str = "",
) -> str:
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    prompt_text = (
        f"请描述当前{('图片' if media_kind == 'image' else '视频')}里发生了什么，重点提取和诈骗识别有关的信息。"
        "只输出简洁中文，不要使用 markdown，不要输出条目符号。"
        "如果看不清楚，就明确说明看不清楚的部分。"
    )
    if file_name:
        prompt_text = f"文件名：{file_name}。" + prompt_text

    url = f"{settings.doubao_ark_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    path_obj = Path(media_path)
    user_content = _user_content_parts(
        prompt_text,
        media_path=path_obj,
        media_kind=media_kind,
    )
    payload: dict[str, Any] = {
        "model": settings.doubao_chat_model,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "你是一个多模态内容理解助手，负责准确描述图片或视频中发生的事情。"},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        raise httpx.HTTPStatusError(
            message=f"{r.status_code} {r.text}",
            request=r.request,
            response=r,
        )

    body = r.json()
    choices = body.get("choices", [])
    if not choices:
        raise ValueError(f"Unexpected media summary response: {str(body)[:300]}")
    message = choices[0].get("message", {})
    content = (message.get("content") or "").strip()
    print(f"content: {content}")
    if not content:
        raise ValueError(f"Empty media summary response: {str(body)[:300]}")
    return content


def transcribe_audio_with_doubao(
    audio_url: str,
    *,
    file_name: str = "",
    audio_path: str | Path | None = None,
) -> str:
    # 优先调用自部署 ASR 微服务（如果配置了地址）
    if settings.asr_service_base_url.strip():
        base = settings.asr_service_base_url.rstrip("/")
        with httpx.Client(timeout=float(settings.asr_service_timeout_sec)) as client:
            path_obj = Path(audio_path) if audio_path else None
            if path_obj and path_obj.exists():
                service_url = f"{base}/transcribe_file"
                file_bytes = path_obj.read_bytes()
                upload_name = file_name or path_obj.name
                mime = _AUDIO_SUFFIX_MIME.get(path_obj.suffix.lower(), "application/octet-stream")
                files = {"file": (upload_name, file_bytes, mime)}
                r = client.post(service_url, files=files)
            else:
                service_url = f"{base}/transcribe_by_url"
                payload = {"audio_url": audio_url, "file_name": file_name or Path(audio_url).name}
                r = client.post(service_url, json=payload)
        if r.status_code != 200:
            raise httpx.HTTPStatusError(
                message=f"{r.status_code} {r.text}",
                request=r.request,
                response=r,
            )
        body = r.json()
        text = str(body.get("text") or "").strip()
        if not text:
            raise ValueError(f"ASR 微服务返回为空：{str(body)[:300]}")
        return text

    api_key = settings.doubao_asr_api_key or settings.doubao_api_key
    if not api_key:
        raise ValueError("DOUBAO_ASR_API_KEY（或 DOUBAO_API_KEY）未配置")
    if not audio_url.strip():
        raise ValueError("音频 URL 不能为空")

    suffix = Path(file_name or "audio.wav").suffix.lower()
    fmt_map = {
        ".mp3": "mp3",
        ".wav": "wav",
        ".ogg": "ogg",
        ".opus": "ogg",
        ".pcm": "raw",
        ".raw": "raw",
        ".m4a": "mp3",
        ".webm": "ogg",
    }
    audio_format = fmt_map.get(suffix, "wav")
    request_id = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": settings.doubao_asr_resource_id,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
    }
    payload: dict[str, Any] = {
        "user": {"uid": "anti_fraud_user"},
        "audio": {
            "url": audio_url,
            "format": audio_format,
            "language": "zh-CN",
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
        },
    }
    with httpx.Client(timeout=180.0) as client:
        r = client.post(settings.doubao_asr_submit_url, headers=headers, json=payload)
    if r.status_code != 200:
        raise httpx.HTTPStatusError(
            message=f"{r.status_code} {r.text}",
            request=r.request,
            response=r,
        )

    body = r.json()
    text_candidates = [
        body.get("text"),
        body.get("result"),
        (body.get("data") or {}).get("text") if isinstance(body.get("data"), dict) else None,
        (body.get("data") or {}).get("result") if isinstance(body.get("data"), dict) else None,
        (body.get("utterances") or [{}])[0].get("text") if isinstance(body.get("utterances"), list) and body.get("utterances") else None,
    ]
    for item in text_candidates:
        text = str(item or "").strip()
        if text:
            return text
    raise ValueError(f"语音识别返回中未找到文本结果：{str(body)[:500]}")


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
        cases_text += f"\n参考案例 {i}（相似度 {case.get('similarity', 0):.1%}）：\n"
        cases_text += f"  {case.get('content', '')}\n"

    system_prompt = """你是一个专业的反诈咨询顾问。你的任务是根据用户提供的情况描述和参考案例，独立分析判断诈骗类型并给出建议。
####################################
重要规则：
1. 你需要根据案例描述和用户输入，自己判断诈骗类型（如：刷单诈骗、冒充公检法、虚假投资、杀猪盘、网购诈骗等）
2. 不要直接使用参考案例中的诈骗类型标签，要根据案例内容特征自行判断
3. 分析用户的情况与案例的相似之处和风险点
4. 提供具体、可行的防范建议
5. 如果用户的情况与案例完全不相关，也要基于反诈专业知识给出建议
6.提出总字数不超过200字
参考案例：""" + cases_text

    user_message = f"""用户的情况描述：
{user_input}
####################################
请根据上述案例分析并回答：
1. 识别用户面临的具体诈骗风险
2. 你的诈骗类型判断及依据（不要使用案例中的标签，要根据内容特征判断）
3. 与参考案例的相似之处和独特风险点
4. 具体的防范措施
5. 如果已经被骗，应该采取的行动

####################################
你必须严格生成以下json格式：
{{
  "overall_judgment":{{
    "conclusion":"基于案例分析和专业知识，给出综合判断结论",
    "fraud_type_rag":"根据案例内容特征自行判断的诈骗类型（如：刷单诈骗、冒充公检法、虚假投资、杀猪盘、网购诈骗、注销校园贷等）",
    "prevention_measures":"具体可行的防范建议",
    "post_fraud_actions":"如果已被骗，应该采取的行动"
  }},
  "rag_result":{{
    "retrieved_case":"简要描述参考案例的核心特征",
    "retrival_reason":"案例与用户情况的关联分析"
  }},
  "personal_info_analysis":{{
    "conclusion":"对用户个人信息的风险评估"
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
    import time as _time_lib; _llm_start = _time_lib.perf_counter()
    print(f"[llm] LLM advice 开始调用")
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)
    print(f"[llm] LLM advice 响应收到, 耗时 {_time_lib.perf_counter()-_llm_start:.3f}s, status={r.status_code}")

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
