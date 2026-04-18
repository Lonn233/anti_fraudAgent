from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import Detect, DetectionReport
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


def _utc_now_naive() -> datetime:
    """UTC 当前时刻；无时区信息，与 SQLite 中 DateTime 存储习惯一致。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc_iso_z(dt: datetime) -> str:
    """将库里的 UTC 朴素时间格式化为带 Z 的 ISO，避免被误当成本地时间。"""
    u = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return u.isoformat(timespec="microseconds").replace("+00:00", "Z")


def ensure_storage() -> Path:
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings.storage_path


def media_relative_path(media_type: str, stored_file_name: str) -> str:
    """入库用的相对路径：/media/{类型}/{磁盘文件名}"""
    mt = media_type.strip().lower()
    return f"/media/{mt}/{stored_file_name}"


def media_absolute_url(relative_path: str) -> str:
    """用全局 public_base_url 拼完整 URL（相对路径须以 / 开头）。"""
    base = settings.public_base_url.rstrip("/")
    rel = relative_path if relative_path.startswith("/") else f"/{relative_path}"
    return f"{base}{rel}"


def _persist_report_and_detect(
    db: Session,
    user_id: int,
    detect_type: str,
    detect_content: str,
    risk_index: float,
    top_case: dict | None,
    llm_result: dict | None,
    source_materials: list[dict] | None = None,
) -> Detect:
    """写入 report + detect；返回 detect 行（含 id、detect_time）。"""
    now = _utc_now_naive()
    draft = build_detect_response(
        report_id="0",
        detect_type=detect_type,
        detect_content=detect_content,
        detect_time=_naive_utc_iso_z(now),
        risk_index=risk_index,
        top_case=top_case,
        llm_result=llm_result,
    )
    rc = draft.report_content
    fraud_type = (rc.overall_judgment.fraud_type_rag or "").strip()
    rep = DetectionReport(
        detect_type=detect_type,
        detect_content=detect_content,
        source_materials=source_materials or [],
        overall_judgment=rc.overall_judgment.model_dump(),
        rag_result=rc.rag_result.model_dump(),
        multimodal_fusion_recognition=rc.multimodal_fusion_recognition.model_dump(),
        personal_info_analysis=rc.personal_info_analysis.model_dump(),
        fraud_type=fraud_type,
        created_at=now,
    )
    db.add(rep)
    db.flush()

    det = Detect(
        user_id=user_id,
        isreport=True,
        report_id=rep.id,
        detect_time=now,
        risk_index=risk_index,
        detect_type=detect_type,
        detect_content=detect_content,
    )
    db.add(det)
    db.commit()
    db.refresh(det)
    db.refresh(rep)
    return det


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


def process_text_detection(
    db: Session,
    user_id: int,
    text: str,
    source_materials: list[dict] | None = None,
) -> DetectOut:
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

    top_case = result["retrieved_cases"][0] if result["retrieved_cases"] else None
    risk_index = round(result["risk_score"] / 10, 1)
    det = _persist_report_and_detect(
        db,
        user_id,
        "text",
        text,
        risk_index,
        top_case,
        llm_result,
        source_materials=source_materials,
    )

    total_elapsed = time.perf_counter() - total_start
    logger.info(
        "[TIMER] detect/text total: %.3fs (rag=%.3fs, llm=%.3fs)",
        total_elapsed,
        rag_elapsed,
        llm_elapsed,
    )

    return build_detect_response(
        report_id=str(det.id),
        detect_type="text",
        detect_content=text,
        detect_time=_naive_utc_iso_z(det.detect_time),
        risk_index=risk_index,
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
    logger.debug(
        "Media saved: name=%s bytes=%s content_type=%s",
        stored_name,
        file_size,
        content_type,
    )

    if media_type == "image":
        result = detect_fraud_by_image_rag(saved_path)
    elif media_type == "video":
        result = detect_fraud_by_video_rag(saved_path)
    else:
        result = {"risk_score": 0, "reasons": [], "retrieved_cases": []}

    logger.info("[TIMER] LLM advice start")
    user_msg = _media_user_message(media_type, original_file_name)
    llm_result = run_llm_advice(
        user_msg,
        result,
        media_path=saved_path if media_type in ("image", "video") else None,
        media_kind=media_type if media_type in ("image", "video") else None,
    )

    top_case = result["retrieved_cases"][0] if result["retrieved_cases"] else None
    risk_index = round(result["risk_score"] / 10, 1)
    detect_content = (
        media_relative_path(media_type, stored_name)
        if media_type in ("image", "video", "audio")
        else original_file_name
    )
    source_materials = [
        {
            "type": media_type,
            "url": detect_content,
            "file_name": original_file_name,
        }
    ]

    det = _persist_report_and_detect(
        db,
        user_id,
        media_type,
        detect_content,
        risk_index,
        top_case,
        llm_result,
        source_materials=source_materials,
    )

    return build_detect_response(
        report_id=str(det.id),
        detect_type=media_type,
        detect_content=detect_content,
        detect_time=_naive_utc_iso_z(det.detect_time),
        risk_index=risk_index,
        top_case=top_case,
        llm_result=llm_result,
    )


def list_user_detection_records(db: Session, user_id: int, limit: int) -> list[dict]:
    limit = max(1, min(200, limit))
    rows = (
        db.query(Detect)
        .filter(Detect.user_id == user_id)
        .order_by(Detect.detect_time.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "kind": r.detect_type,
            "risk_score": int(round(r.risk_index * 10)),
            "risk_index": r.risk_index,
            "report_id": r.report_id,
            "created_at": r.detect_time,
            "detect_content": r.detect_content,
        }
        for r in rows
    ]
