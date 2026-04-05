from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import DetectionRecord
from app.schemas import (
    DetectMetaDataOut,
    DetectMultimodalFusionRecognitionOut,
    DetectOut,
    DetectOverallJudgmentOut,
    DetectPersonalInfoAnalysisOut,
    DetectRagResultOut,
    DetectReportContentOut,
)
from app.services.llm import generate_fraud_advice
from app.utils.rag import detect_fraud_by_image_rag, detect_fraud_by_rag, detect_fraud_by_video_rag

logger = logging.getLogger(__name__)


def ensure_storage() -> Path:
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings.storage_path


def save_record(
    db: Session,
    user_id: int,
    kind: str,
    result: dict,
    input_text: str | None = None,
    file_path: str | None = None,
    file_name: str | None = None,
    content_type: str | None = None,
    extra: dict | None = None,
) -> DetectionRecord:
    result_data = {
        "reasons": result.get("reasons", []),
        "retrieved_cases": result.get("retrieved_cases", []),
        "method": "rag_vector_search",
    }
    if extra:
        result_data.update(extra)

    rec = DetectionRecord(
        user_id=user_id,
        kind=kind,
        input_text=input_text,
        file_path=file_path,
        file_name=file_name,
        content_type=content_type,
        risk_score=int(result.get("risk_score", 0)),
        result_json=json.dumps(result_data, ensure_ascii=False),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def build_detect_response(
    report_id: str,
    detect_type: str,
    detect_content: str,
    detect_time: str,
    risk_index: float,
    top_case: dict | None,
    llm_result: dict | None,
) -> DetectOut:
    top_case = top_case or {}
    llm_result = llm_result or {}
    overall = llm_result.get("overall_judgment", {})
    rag_llm = llm_result.get("rag_result", {})
    personal = llm_result.get("personal_info_analysis", {})

    return DetectOut(
        risk_index=risk_index,
        isReport=True,
        report_content=DetectReportContentOut(
            meta_data=DetectMetaDataOut(
                report_id=report_id,
                detect_type=detect_type,
                detect_content=detect_content,
                detect_time=detect_time,
            ),
            overall_judgment=DetectOverallJudgmentOut(
                risk_index=None,
                fraud_type_rag=str(overall.get("fraud_type_rag", "") or ""),
                conclusion=str(overall.get("conclusion", "") or ""),
                prevention_measures=str(overall.get("prevention_measures", "") or ""),
                post_fraud_actions=str(overall.get("post_fraud_actions", "") or ""),
            ),
            rag_result=DetectRagResultOut(
                retrieved_case=str(rag_llm.get("retrieved_case", "") or top_case.get("content", "") or ""),
                similarity=float(top_case.get("similarity", 0.0) or 0.0),
                retrieval_reason=str(rag_llm.get("retrival_reason", "") or rag_llm.get("retrieval_reason", "") or ""),
            ),
            multimodal_fusion_recognition=DetectMultimodalFusionRecognitionOut(
                ai_synthesis_probability=None,
                judgment_reason="",
            ),
            personal_info_analysis=DetectPersonalInfoAnalysisOut(
                conclusion=str(personal.get("conclusion", "") or ""),
            ),
        ),
    )


def _fallback_llm_result(result: dict) -> dict:
    return {
        "overall_judgment": {
            "fraud_type_rag": result["retrieved_cases"][0].get("fraud_type", "")
            if result["retrieved_cases"]
            else "",
            "conclusion": "",
            "prevention_measures": "",
            "post_fraud_actions": "",
        },
        "rag_result": {"retrival_reason": ""},
        "personal_info_analysis": {"conclusion": ""},
    }


def run_llm_advice(
    user_input: str,
    result: dict,
    *,
    media_path: Path | None = None,
    media_kind: str | None = None,
) -> dict:
    llm_start = time.perf_counter()
    try:
        mk: Literal["image", "video"] | None = None
        if media_kind == "image":
            mk = "image"
        elif media_kind == "video":
            mk = "video"
        llm_result = generate_fraud_advice(
            user_input,
            result["retrieved_cases"],
            media_path=media_path if mk else None,
            media_kind=mk,
        )
        logger.info("[TIMER] LLM advice done: %.3fs", time.perf_counter() - llm_start)
        return llm_result
    except Exception as e:
        logger.warning(
            "[TIMER] LLM advice failed after %.3fs: %s",
            time.perf_counter() - llm_start,
            e,
        )
        return _fallback_llm_result(result)


def process_text_detection(db: Session, user_id: int, text: str) -> DetectOut:
    total_start = time.perf_counter()
    logger.info("[TIMER] RAG detection start for user %d", user_id)
    rag_start = time.perf_counter()
    result = detect_fraud_by_rag(text)
    rag_elapsed = time.perf_counter() - rag_start
    logger.info(
        "[TIMER] RAG detection done: %.3fs (risk_score=%d, cases=%d)",
        rag_elapsed,
        result["risk_score"],
        len(result["retrieved_cases"]),
    )

    logger.info("[TIMER] LLM advice start")
    llm_start = time.perf_counter()
    llm_result = run_llm_advice(text, result)
    llm_elapsed = time.perf_counter() - llm_start

    rec = save_record(
        db,
        user_id,
        "text",
        result,
        input_text=text,
        extra={"llm_result": llm_result},
    )

    total_elapsed = time.perf_counter() - total_start
    logger.info(
        "[TIMER] detect/text total: %.3fs (rag=%.3fs, llm=%.3fs)",
        total_elapsed,
        rag_elapsed,
        llm_elapsed,
    )

    top_case = result["retrieved_cases"][0] if result["retrieved_cases"] else None
    return build_detect_response(
        report_id=str(rec.id),
        detect_type="text",
        detect_content=text,
        detect_time=rec.created_at.isoformat(),
        risk_index=round(result["risk_score"] / 10, 1),
        top_case=top_case,
        llm_result=llm_result,
    )


def _media_user_message(media_type: str, original_file_name: str) -> str:
    return f"用户上传了{media_type}类型文件，文件名：{original_file_name}。请结合多模态检索到的相似案例进行分析。"


def process_saved_media_detection(
    db: Session,
    user_id: int,
    media_type: str,
    saved_path: Path,
    original_file_name: str,
    stored_name: str,
    file_size: int,
    content_type: str | None,
) -> DetectOut:
    if media_type == "image":
        result = detect_fraud_by_image_rag(saved_path)
    elif media_type == "video":
        result = detect_fraud_by_video_rag(saved_path)
    else:
        result = {"risk_score": 0, "reasons": [], "retrieved_cases": []}

    rec = save_record(
        db,
        user_id,
        media_type,
        result,
        file_path=str(saved_path),
        file_name=original_file_name,
        content_type=content_type,
        extra={"saved_name": stored_name, "bytes": file_size},
    )

    logger.info("[TIMER] LLM advice start")
    user_msg = _media_user_message(media_type, original_file_name)
    llm_result = run_llm_advice(
        user_msg,
        result,
        media_path=saved_path if media_type in ("image", "video") else None,
        media_kind=media_type if media_type in ("image", "video") else None,
    )

    top_case = result["retrieved_cases"][0] if result["retrieved_cases"] else None
    return build_detect_response(
        report_id=str(rec.id),
        detect_type=media_type,
        detect_content=original_file_name,
        detect_time=rec.created_at.isoformat(),
        risk_index=round(result["risk_score"] / 10, 1),
        top_case=top_case,
        llm_result=llm_result,
    )


def list_user_detection_records(db: Session, user_id: int, limit: int) -> list[dict]:
    limit = max(1, min(200, limit))
    rows = (
        db.query(DetectionRecord)
        .filter(DetectionRecord.user_id == user_id)
        .order_by(DetectionRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "risk_score": r.risk_score,
            "created_at": r.created_at,
            "file_name": r.file_name,
            "content_type": r.content_type,
        }
        for r in rows
    ]
