from __future__ import annotations

import logging
from typing import TypedDict

from pymilvus import Collection

from app.config.settings import settings
from app.services.doubao_embed import embed_texts
from app.services.milvus_text import _ensure_connection

logger = logging.getLogger(__name__)


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


def detect_fraud_by_rag(text: str) -> DetectionResult:
    """
    基于 RAG（检索增强生成）的反诈检测。
    
    流程：
    1. 对输入文本进行向量化
    2. 在 Milvus 中检索相似的诈骗案例
    3. 根据相似度计算风险分数
    
    Args:
        text: 待检测的文本
        
    Returns:
        DetectionResult: 包含风险分数、原因和检索案例的结果
        
    Raises:
        ValueError: 向量化或检索失败
    """
    logger.info("Starting RAG-based fraud detection")
    
    # 第一步：向量化输入文本
    logger.info("Embedding input text")
    vectors = embed_texts([text])
    if not vectors:
        raise ValueError("Failed to embed text")
    input_vector = vectors[0]

    # 第二步：在 Milvus 中检索相似案例
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

    # 第三步：解析检索结果并计算风险分数
    reasons: list[str] = []
    retrieved_cases: list[RetrievedCase] = []
    risk_score = 0

    if search_results and len(search_results) > 0:
        hits = search_results[0]
        for hit in hits:
            # COSINE 距离范围 [-1, 1]，越接近 1 越相似
            distance = hit.distance
            similarity = (distance + 1) / 2  # 转换为 [0, 1] 范围
            
            # 提取字段
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
            
            # 根据相似度计算风险分数
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

    logger.info("Detection completed: risk_score=%d, cases=%d", risk_score, len(retrieved_cases))

    return {
        "risk_score": risk_score,
        "reasons": reasons,
        "retrieved_cases": retrieved_cases,
    }
