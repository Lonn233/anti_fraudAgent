from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# 公共接口
# --------------------------------------------------------------------------- #

def embed_texts(texts: list[str]) -> list[list[float]]:
    """对多条文本逐一调用多模态嵌入接口，返回向量列表。"""
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")
    return [_embed_single(t) for t in texts]


# --------------------------------------------------------------------------- #
# 内部实现
# --------------------------------------------------------------------------- #

def _call_embed_api(input_items: list[dict]) -> list[float]:
    """通用请求方法：向火山方舟多模态嵌入接口发送请求并解析向量。

    Args:
        input_items: 符合接口规范的 input 列表，例如：
            [{"text": "...", "type": "text"}]
            [{"image_url": "data:image/jpeg;base64,...", "type": "image_url"}]
            [{"video_url": "data:video/mp4;base64,...", "type": "video_url"}]

    Returns:
        嵌入向量（float 列表）
    """
    url = f"{settings.doubao_ark_base_url.rstrip('/')}/embeddings/multimodal"
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.doubao_embedding_model,
        "input": input_items,
    }

    logger.info("Doubao embed: url=%s model=%s input_type=%s",
                url, settings.doubao_embedding_model, input_items[0].get("type"))

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)

    logger.info("Doubao response: status=%s body_prefix=%s", r.status_code, r.text[:200])

    if r.status_code != 200:
        #这里的error是处理火山方舟接口返回的错误信息
        raise httpx.HTTPStatusError(
            message=f"{r.status_code} {r.text}",
            request=r.request,
            response=r,
        )

    body = r.json()
    data = body.get("data")

    # 豆包多模态接口：data 是单个 dict {"embedding": [...], "object": "embedding"}
    if isinstance(data, dict):
        emb = data.get("embedding")
        if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
            return [float(x) for x in emb]
        raise ValueError(f"data dict has no valid embedding field: {str(data)[:200]}")

    # 普通 OpenAI 兼容接口：data 是列表 [{"embedding": [...], "index": 0}]
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict):
            emb = item.get("embedding")
            if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
                return [float(x) for x in emb]
    raise ValueError(f"Unexpected embeddings response structure: {str(body)[:300]}")


def _embed_single(text: str) -> list[float]:
    """对单条文本调用多模态嵌入接口，返回向量。"""
    return _call_embed_api([{"text": text, "type": "text"}])


def _embed_image(image_path: str | Path) -> list[float]:
    """对本地图片文件调用多模态嵌入接口，返回向量。

    Args:
        image_path: 本地图片文件路径（支持 jpg/png/webp 等）

    Returns:
        嵌入向量（float 列表）
    """
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # 根据后缀推断 MIME 类型
    suffix = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    mime = mime_map.get(suffix, "image/jpeg")

    # 读取并 Base64 编码
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    image_url = f"data:{mime};base64,{b64}"

    logger.info("Embedding image: path=%s size=%d bytes", path.name, len(raw))

    return _call_embed_api([{"type": "image_url", "image_url": {"url": image_url}}])


def _embed_video(video_path: str | Path) -> list[float]:
    """对本地视频文件调用多模态嵌入接口，返回向量。

    注意：视频文件通常较大，建议控制在接口允许的大小限制内。

    Args:
        video_path: 本地视频文件路径（支持 mp4/avi/mov 等）

    Returns:
        嵌入向量（float 列表）
    """
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # 根据后缀推断 MIME 类型
    suffix = path.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".avi": "video/avi",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".flv": "video/x-flv",
    }
    mime = mime_map.get(suffix, "video/mp4")

    # 读取并 Base64 编码
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    video_url = f"data:{mime};base64,{b64}"

    logger.info("Embedding video: path=%s size=%d bytes", path.name, len(raw))

    return _call_embed_api([{"type": "video_url", "video_url": {"url": video_url}}])
