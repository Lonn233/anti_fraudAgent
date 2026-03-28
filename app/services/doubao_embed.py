from __future__ import annotations

import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """调用火山方舟多模态嵌入接口（doubao-embedding-vision）。

    接口地址：POST {doubao_ark_base_url}/embeddings/multimodal
    input 格式：[{"text": "..."}, ...]  （每项必须是对象，不能是裸字符串）

    注意：多模态接口 data 字段为单个 embedding 对象（dict），而非列表。
    当 texts 有多条时，需逐条调用。
    """
    if not settings.doubao_api_key:
        raise ValueError("DOUBAO_API_KEY is not configured")

    results: list[list[float]] = []
    for text in texts:
        vec = _embed_single(text)
        results.append(vec)
    return results


def _embed_single(text: str) -> list[float]:
    """对单条文本调用多模态嵌入接口，返回向量。"""
    url = f"{settings.doubao_ark_base_url.rstrip('/')}/embeddings/multimodal"
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.doubao_embedding_model,
        "input": [{"text": text,"type":"text"}],
    }

    logger.info("Doubao embed: url=%s model=%s", url, settings.doubao_embedding_model)

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)

    logger.info("Doubao response: status=%s body_prefix=%s", r.status_code, r.text[:200])

    if r.status_code != 200:
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
