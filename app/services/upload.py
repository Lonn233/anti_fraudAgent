from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.services.doubao_embed import embed_texts
from app.services.milvus_text import insert_text_chunks
from app.services.text_chunk import chunk_text

logger = logging.getLogger(__name__)


def extract_text_from_file(file_path: str | Path) -> str:
    """从支持的文件格式中提取文本。

    支持格式：
    - .txt：纯文本
    - .md：Markdown
    - .docx：Word 文档

    Args:
        file_path: 文件路径

    Returns:
        提取的文本内容

    Raises:
        ValueError: 不支持的文件格式
        FileNotFoundError: 文件不存在
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    # .txt 和 .md：直接读取
    if suffix in {".txt", ".md"}:
        logger.info("Extracting text from %s", suffix)
        return path.read_text(encoding="utf-8")

    # .docx：使用 python-docx
    if suffix == ".docx":
        logger.info("Extracting text from docx")
        try:
            from docx import Document
        except ImportError:
            raise ValueError("python-docx not installed. Run: pip install python-docx")

        doc = Document(path)
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        return "\n\n".join(text_parts)

    raise ValueError(f"Unsupported file format: {suffix}. Supported: .txt, .md, .docx")


def upload_and_chunk_file(
    user_id: int,
    file_path: str | Path,
) -> dict:
    """上传文件、提取文本、分段、嵌入、写入 Milvus。

    Args:
        user_id: 用户 ID
        file_path: 文件路径

    Returns:
        包含 doc_id、chunk_count、inserted 的字典

    Raises:
        ValueError: 文件格式不支持或处理失败
    """
    logger.info("Processing file: %s", file_path)

    # 第一步：提取文本
    logger.info("Extracting text from file")
    text = extract_text_from_file(file_path)
    if not text.strip():
        raise ValueError("File is empty or contains no text")

    # 第二步：分段
    logger.info("Chunking text")
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No text chunks produced")

    logger.info("Produced %d chunks", len(chunks))

    # 第三步：向量化
    logger.info("Embedding %d chunks", len(chunks))
    vectors = embed_texts(chunks)
    if not vectors or len(vectors) != len(chunks):
        raise ValueError(f"Embedding mismatch: got {len(vectors)}, expected {len(chunks)}")

    # 第四步：生成 doc_id 并准备元数据
    doc_id = uuid.uuid4().hex
    ages = [0] * len(chunks)  # INT32：默认 0
    jobs = [""] * len(chunks)  # VARCHAR：默认空字符串
    regions = [""] * len(chunks)  # VARCHAR：默认空字符串
    fraud_types = [""] * len(chunks)  # VARCHAR：默认空字符串
    fraud_amounts = [0.0] * len(chunks)  # FLOAT：默认 0.0

    # 第五步：写入 Milvus
    logger.info("Inserting %d chunks into Milvus", len(chunks))
    inserted = insert_text_chunks(
        user_id=user_id,
        doc_id=doc_id,
        chunks=chunks,
        vectors=vectors,
        ages=ages,
        jobs=jobs,
        regions=regions,
        fraud_types=fraud_types,
        fraud_amounts=fraud_amounts,
    )

    logger.info("File processed: doc_id=%s chunks=%d inserted=%d", doc_id, len(chunks), inserted)

    return {
        "doc_id": doc_id,
        "chunk_count": len(chunks),
        "inserted": inserted,
    }
