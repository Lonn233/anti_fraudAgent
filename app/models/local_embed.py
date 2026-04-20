from __future__ import annotations

import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer

from app.config.settings import settings

logger = logging.getLogger(__name__)

_model_cache: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model_cache
    if _model_cache is None:
        logger.info("Loading SentenceTransformer model: %s", settings.sentence_transformer_model)
        _model_cache = SentenceTransformer(settings.sentence_transformer_model)
        logger.info("Model loaded successfully")
    return _model_cache


def embed_texts_local(texts: list[str]) -> list[list[float]]:
    """用本地 SentenceTransformer 模型对文本列表进行向量化。

    模型会自动 L2 归一化，输出向量维度为 512（BAAI/bge-small-zh-v1.5）。
    """
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()
