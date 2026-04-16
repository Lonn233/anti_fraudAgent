from __future__ import annotations

import logging
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas import TextKbUploadIn, TextKbUploadOut, TextReportIn
from app.models.doubao_embed import embed_texts
from app.utils.milvus_text import insert_text_chunks
from app.services.upload import upload_and_chunk_file
from app.utils.deps import get_current_user

router = APIRouter(prefix="/kb", tags=["knowledge"])
logger = logging.getLogger(__name__)


def _ensure_storage() -> Path:
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings.storage_path


# --------------------------------------------------------------------------- #
# /report/text：上传单个案例报告（不分段）
# --------------------------------------------------------------------------- #

@router.post("/report/text", response_model=TextKbUploadOut)
def upload_report_text(
    payload: TextReportIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传单个诈骗案例报告（不分段，一个报告一个向量）。"""
    if not settings.doubao_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 DOUBAO_API_KEY",
        )

    doc_id = (payload.doc_id or "").strip() or uuid.uuid4().hex

    try:
        # 不分段，直接向量化整个文本
        logger.info("Embedding report text for user %d", current.id)
        vectors = embed_texts([payload.text])
        if not vectors:
            raise ValueError("Failed to embed text")

        # 插入 Milvus（一个报告作为一个 chunk）
        logger.info("Inserting into Milvus")
        inserted = insert_text_chunks(
            user_id=current.id,
            doc_id=doc_id,
            chunks=[payload.text],
            vectors=vectors,
            ages=[payload.age],
            jobs=[payload.job],
            regions=[payload.region],
            fraud_types=[payload.fraud_type],
            fraud_amounts=[payload.fraud_amount],
        )

        logger.info("Report uploaded: user=%d doc_id=%s", current.id, doc_id)

        return TextKbUploadOut(
            doc_id=doc_id,
            chunk_count=1,
            inserted=inserted,
            milvus_collection=settings.milvus_collection,
            embedding_model=settings.doubao_embedding_model,
        )

    except httpx.HTTPStatusError as e:
        body_text = e.response.text if hasattr(e, "response") and e.response is not None else str(e)
        logger.error("Embedding API error: %s", body_text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"向量化接口错误：{body_text[:800]}",
        ) from e
    except ValueError as e:
        logger.error("Embedding error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Report upload error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"上传失败：{e}",
        ) from e


# --------------------------------------------------------------------------- #
# /upload/text：上传文件进行分段嵌入（支持 txt、md、docx）
# --------------------------------------------------------------------------- #

@router.post("/upload/text", response_model=TextKbUploadOut)
async def upload_text_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传文本文件进行分段嵌入（按段落分段，每段一个向量）。
    
    支持格式：.txt、.md、.docx
    自动提取文本、分段、嵌入、写入 Milvus。
    """
    if not settings.doubao_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 DOUBAO_API_KEY",
        )

    # 检查文件格式
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".docx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件格式，仅支持 .txt、.md、.docx",
        )

    # 保存临时文件
    storage = _ensure_storage()
    upload_dir = storage / "upload_text"
    upload_dir.mkdir(exist_ok=True)
    temp_name = f"upload_{uuid.uuid4().hex}{suffix}"
    temp_path = upload_dir / temp_name

    try:
        # 保存上传的文件
        size = 0
        max_bytes = settings.max_upload_mb * 1024 * 1024
        with temp_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件过大（超过 {settings.max_upload_mb}MB）",
                    )
                f.write(chunk)

        logger.info("File saved: %s size=%d bytes", temp_name, size)

        # 调用 upload service 处理文件
        logger.info("Processing file for user %d", current.id)
        result = upload_and_chunk_file(current.id, temp_path)

        logger.info("File upload done: user=%d doc_id=%s chunks=%d", 
                   current.id, result["doc_id"], result["chunk_count"])

        return TextKbUploadOut(
            doc_id=result["doc_id"],
            chunk_count=result["chunk_count"],
            inserted=result["inserted"],
            milvus_collection=settings.milvus_collection,
            embedding_model=settings.doubao_embedding_model,
        )

    except httpx.HTTPStatusError as e:
        body_text = e.response.text if hasattr(e, "response") and e.response is not None else str(e)
        logger.error("Embedding API error: %s", body_text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"向量化接口错误：{body_text[:800]}",
        ) from e
    except ValueError as e:
        logger.error("File processing error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("File upload error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败：{e}",
        ) from e
    finally:
        # 清理临时文件（可选，注释掉以保留上传的文件）
        # if temp_path.exists():
        #     try:
        #         temp_path.unlink()
        #         logger.info("Temp file deleted: %s", temp_name)
        #     except Exception as e:
        #         logger.warning("Failed to delete temp file: %s", e)
        pass
