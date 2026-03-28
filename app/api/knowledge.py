from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.config.settings import settings
from app.db.models import User
from app.schemas import TextKbUploadIn, TextKbUploadOut
from app.services.doubao_embed import embed_texts
from app.services.milvus_text import insert_text_chunks
from app.services.text_chunk import chunk_text
from app.utils.deps import get_current_user

router = APIRouter(prefix="/kb", tags=["knowledge"])
logger = logging.getLogger(__name__)


@router.post("/text/upload", response_model=TextKbUploadOut)
def upload_text_to_milvus(
    payload: TextKbUploadIn,
    current: User = Depends(get_current_user),
):
    if not settings.doubao_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DOUBAO_API_KEY is not configured",
        )

    max_c = payload.chunk_max_chars or settings.kb_chunk_max_chars
    overlap = payload.chunk_overlap_chars or settings.kb_chunk_overlap_chars
    if overlap >= max_c:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chunk_overlap_chars must be smaller than chunk_max_chars",
        )

    chunks = chunk_text(payload.text, max_c, overlap)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text chunks produced",
        )

    doc_id = (payload.doc_id or "").strip() or uuid.uuid4().hex

    try:
        vectors = embed_texts(chunks)
    except httpx.HTTPStatusError as e:
        body_text = e.response.text if hasattr(e, "response") and e.response is not None else str(e)
        logger.error("Doubao embed HTTP error: %s", body_text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding API error: {body_text[:800]}",
        ) from e
    except ValueError as e:
        logger.error("Doubao embed value error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Doubao embed unexpected error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding unexpected error: {e}",
        ) from e

    try:
        inserted = insert_text_chunks(
            current.id,
            doc_id,
            chunks,
            vectors,
            age=payload.age,
            job=payload.job,
            region=payload.region,
            fraud_type=payload.fraud_type,
            fraud_amount=payload.fraud_amount,
        )
    except Exception as e:
        logger.exception("Milvus insert error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Milvus insert failed: {e}",
        ) from e

    return TextKbUploadOut(
        doc_id=doc_id,
        chunk_count=len(chunks),
        inserted=inserted,
        milvus_collection=settings.milvus_collection,
        embedding_model=settings.doubao_embedding_model,
    )
