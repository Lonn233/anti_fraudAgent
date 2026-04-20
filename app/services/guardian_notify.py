from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Guardian, GuardianAlert

logger = logging.getLogger(__name__)

# 触发预警的风险等级阈值
_ALERT_THRESHOLD_LEVELS = {"medium", "high"}


def _risk_level_key(risk_index: float) -> str:
    if risk_index >= 7.5:
        return "high"
    if risk_index >= 5.0:
        return "medium"
    if risk_index >= 2.5:
        return "low"
    return "none"


def notify_guardians(
    db: Session,
    ward_user_id: int,
    content: str,
    risk_index: float,
    detect_report_id: int | None = None,
) -> list[dict[str, Any]]:
    """向被监护人的所有监护人发送预警。

    仅当风险等级为 medium 或 high 时才创建预警记录。

    Args:
        db: 数据库会话
        ward_user_id: 被监护人用户 ID（即触发预警的人）
        content: 预警内容摘要（取 AI 回复的前 512 字符）
        risk_index: 综合风险评分（0-10）
        detect_report_id: 关联的检测报告 ID（可选）

    Returns:
        已创建的预警记录列表，每条含 guardian_id、monitor_id、alert_id
    """
    risk_level = _risk_level_key(risk_index)
    if risk_level not in _ALERT_THRESHOLD_LEVELS:
        logger.info(
            "[ALERT] risk_index=%.1f (level=%s) skipped for ward_id=%d",
            risk_index,
            risk_level,
            ward_user_id,
        )
        return []

    # ward_user_id 在 Guardian 表中存储在 ward_id 字段
    guardians = (
        db.query(Guardian)
        .filter(Guardian.ward_id == ward_user_id)
        .all()
    )
    if not guardians:
        logger.info(
            "[ALERT] No guardians found for ward_id=%d, skipping notification",
            ward_user_id,
        )
        return []

    created: list[dict[str, Any]] = []
    for g in guardians:
        alert = GuardianAlert(
            ward_id=ward_user_id,
            guardian_id=g.id,
            detect_report_id=detect_report_id,
            content=content[:512],
            risk_level=risk_level,
            risk_index=risk_index,
            is_read=False,
        )
        db.add(alert)
        db.flush()
        created.append({
            "guardian_id": g.monitor_id,
            "monitor_id": g.monitor_id,
            "alert_id": alert.id,
            "risk_level": risk_level,
            "risk_index": risk_index,
        })
        logger.info(
            "[ALERT] Created alert id=%d for guardian_id=%d (monitor_id=%d), ward_id=%d",
            alert.id,
            g.monitor_id,
            g.monitor_id,
            ward_user_id,
        )

    db.commit()
    return created


def get_unread_alerts(
    db: Session,
    guardian_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """获取指定监护人所有未读的预警列表（供监护人页面轮询）。"""
    rows = (
        db.query(GuardianAlert)
        .filter(
            GuardianAlert.guardian_id == guardian_id,
            GuardianAlert.is_read == False,  # noqa: E712
        )
        .order_by(GuardianAlert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_alert_to_dict(r) for r in rows]


def get_all_alerts(
    db: Session,
    guardian_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """获取指定监护人所有预警列表（已读+未读，供监护人页面展示）。"""
    rows = (
        db.query(GuardianAlert)
        .filter(GuardianAlert.guardian_id == guardian_id)
        .order_by(GuardianAlert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_alert_to_dict(r) for r in rows]


def mark_alerts_read(
    db: Session,
    guardian_id: int,
    alert_ids: list[int] | None = None,
) -> int:
    """标记预警为已读。传入 alert_ids 时仅标记指定记录；否则标记该监护人所有未读。"""
    q = db.query(GuardianAlert).filter(GuardianAlert.guardian_id == guardian_id)
    if alert_ids:
        q = q.filter(GuardianAlert.id.in_(alert_ids))
    else:
        q = q.filter(GuardianAlert.is_read == False)  # noqa: E712
    count = q.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return count


def _alert_to_dict(alert: GuardianAlert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "ward_id": alert.ward_id,
        "guardian_id": alert.guardian_id,
        "detect_report_id": alert.detect_report_id,
        "content": alert.content,
        "risk_level": alert.risk_level,
        "risk_index": alert.risk_index,
        "is_read": alert.is_read,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }
