from __future__ import annotations

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config.settings import settings

_MILVUS_CONNECTED = False


def _ensure_connection() -> None:
    global _MILVUS_CONNECTED
    if _MILVUS_CONNECTED:
        return
    kwargs: dict = {"uri": settings.milvus_uri}
    if settings.milvus_token:
        kwargs["token"] = settings.milvus_token
    connections.connect(alias="default", **kwargs)
    _MILVUS_CONNECTED = True


def ensure_text_collection_exists() -> None:
    _ensure_connection()
    name = settings.milvus_collection
    if utility.has_collection(name):
        return

    dim = settings.milvus_embedding_dim
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="user_id", dtype=DataType.INT64),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="chunk_index", dtype=DataType.INT32),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        # 可选字段：用户信息
        FieldSchema(name="age", dtype=DataType.INT32, nullable=True),
        FieldSchema(name="job", dtype=DataType.VARCHAR, max_length=128, nullable=True),
        FieldSchema(name="region", dtype=DataType.VARCHAR, max_length=128, nullable=True),
        # 可选字段：诈骗案例信息
        FieldSchema(name="fraud_type", dtype=DataType.VARCHAR, max_length=128, nullable=True),
        FieldSchema(name="fraud_amount", dtype=DataType.FLOAT, nullable=True),
    ]
    schema = CollectionSchema(fields, description="anti-fraud KB text chunks with user and fraud info")
    col = Collection(name=name, schema=schema)
    col.create_index(
        field_name="embedding",
        index_params={"index_type": "AUTOINDEX", "metric_type": "COSINE"},
    )


def insert_text_chunks(
    user_id: int,
    doc_id: str,
    chunks: list[str],
    vectors: list[list[float]],
    ages: list[int | None] | None = None,
    jobs: list[str | None] | None = None,
    regions: list[str | None] | None = None,
    fraud_types: list[str | None] | None = None,
    fraud_amounts: list[float | None] | None = None,
) -> int:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")

    _ensure_connection()
    ensure_text_collection_exists()
    name = settings.milvus_collection
    col = Collection(name)

    dim = settings.milvus_embedding_dim
    for v in vectors:
        if len(v) != dim:
            raise ValueError(
                f"Vector dim {len(v)} != MILVUS_EMBEDDING_DIM ({dim}); "
                "请调整 .env 中 MILVUS_EMBEDDING_DIM 与模型输出维度一致。"
            )

    user_ids = [user_id] * len(chunks)
    doc_ids = [doc_id] * len(chunks)
    chunk_indices = list(range(len(chunks)))
    
    # 如果未提供，使用 None 填充
    ages = ages or [None] * len(chunks)
    jobs = jobs or [None] * len(chunks)
    regions = regions or [None] * len(chunks)
    fraud_types = fraud_types or [None] * len(chunks)
    fraud_amounts = fraud_amounts or [None] * len(chunks)

    col.insert(
        [
            user_ids,
            doc_ids,
            chunk_indices,
            chunks,
            vectors,
            ages,
            jobs,
            regions,
            fraud_types,
            fraud_amounts,
        ]
    )
    col.flush()
    return len(chunks)
