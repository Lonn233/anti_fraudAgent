from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

from pymilvus import Collection

from app.config.settings import settings
from app.models.doubao_embed import _embed_image, _embed_single, _embed_video, embed_texts
from app.utils.milvus_text import _ensure_connection

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# TypedDict
# --------------------------------------------------------------------------- #

class RetrievedCase(TypedDict):
    """检索到的诈骗案例"""
    doc_id: str
    content: str
    fraud_type: str
    fraud_amount: float | None
    age: int | None
    job: str | None
    region: str | None
    similarity: float


class DetectionResult(TypedDict):
    """检测结果"""
    risk_score: int
    reasons: list[str]
    retrieved_cases: list[RetrievedCase]


# --------------------------------------------------------------------------- #
# 公共：Milvus 检索 + 风险计算
# --------------------------------------------------------------------------- #

def _search_and_score(input_vector: list[float]) -> DetectionResult:
    """对输入向量在 Milvus 中检索相似案例，并计算风险分数。

    供文本、图片、视频三个 RAG 函数共用。

    Args:
        input_vector: 已经过嵌入的查询向量

    Returns:
        DetectionResult
    """
    logger.info("Searching Milvus for similar cases")
    _ensure_connection()
    col = Collection(settings.milvus_collection)

    search_results = col.search(
        data=[input_vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=5,
        output_fields=[
            "user_id",
            "doc_id",
            "content",
            "age",
            "job",
            "region",
            "fraud_type",
            "fraud_amount",
        ],
    )

    reasons: list[str] = []
    retrieved_cases: list[RetrievedCase] = []
    risk_score = 0

    if search_results and len(search_results) > 0:
        for hit in search_results[0]:
            # COSINE 距离范围 [-1, 1]，越接近 1 越相似
            similarity = (hit.distance + 1) / 2  # 转换为 [0, 1]

            entity = hit.entity
            case_info: RetrievedCase = {
                "doc_id": entity.get("doc_id", "unknown"),
                "content": entity.get("content", "")[:100],
                "fraud_type": entity.get("fraud_type", "未知"),
                "fraud_amount": entity.get("fraud_amount"),
                "age": entity.get("age"),
                "job": entity.get("job"),
                "region": entity.get("region"),
                "similarity": round(similarity, 3),
            }
            retrieved_cases.append(case_info)

            if similarity > 0.7:
                risk_score = max(risk_score, 85)
                reasons.append(
                    f"高度相似案例（相似度 {similarity:.1%}）：{case_info['fraud_type']}"
                )
            elif similarity > 0.5:
                risk_score = max(risk_score, 60)
                reasons.append(
                    f"中等相似案例（相似度 {similarity:.1%}）：{case_info['fraud_type']}"
                )
            else:
                risk_score = max(risk_score, 30)
                reasons.append(
                    f"低相似案例（相似度 {similarity:.1%}）：{case_info['fraud_type']}"
                )

    if not reasons:
        risk_score = 10
        reasons = ["未发现相似诈骗案例，风险较低"]

    logger.info("Search completed: risk_score=%d, cases=%d", risk_score, len(retrieved_cases))

    return {
        "risk_score": risk_score,
        "reasons": reasons,
        "retrieved_cases": retrieved_cases,
    }


# --------------------------------------------------------------------------- #
# 文本 RAG
# --------------------------------------------------------------------------- #

def detect_fraud_by_rag(text: str) -> DetectionResult:
    """基于文本的反诈 RAG 检测。

    Args:
        text: 待检测的文本内容

    Returns:
        DetectionResult
    """
    import time
    logger.info("RAG detect: text")

    embed_start = time.perf_counter()
    vectors = embed_texts([text])
    embed_elapsed = time.perf_counter() - embed_start
    logger.info("[TIMER] embed_texts: %.3fs", embed_elapsed)

    if not vectors:
        raise ValueError("Failed to embed text")

    search_start = time.perf_counter()
    result = _search_and_score(vectors[0])
    search_elapsed = time.perf_counter() - search_start
    logger.info("[TIMER] milvus search+score: %.3fs", search_elapsed)

    return result


# --------------------------------------------------------------------------- #
# 图片 RAG
# --------------------------------------------------------------------------- #

def detect_fraud_by_image_rag(image_path: str | Path) -> DetectionResult:
    """基于图片的反诈 RAG 检测。

    将图片 Base64 编码后调用豆包多模态嵌入，再在 Milvus 中检索相似案例。

    Args:
        image_path: 本地图片文件路径

    Returns:
        DetectionResult
    """
    logger.info("RAG detect: image path=%s", image_path)
    input_vector = _embed_image(image_path)
    return _search_and_score(input_vector)


# --------------------------------------------------------------------------- #
# 视频 RAG
# --------------------------------------------------------------------------- #

def detect_fraud_by_video_rag(video_path: str | Path) -> DetectionResult:
    """基于视频的反诈 RAG 检测。

    将视频 Base64 编码后调用豆包多模态嵌入，再在 Milvus 中检索相似案例。

    Args:
        video_path: 本地视频文件路径

    Returns:
        DetectionResult
    """
    logger.info("RAG detect: video path=%s", video_path)
    input_vector = _embed_video(video_path)
    return _search_and_score(input_vector)
