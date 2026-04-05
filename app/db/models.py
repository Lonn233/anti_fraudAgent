from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)

    guardians: Mapped[list["Guardian"]] = relationship(
        back_populates="ward", cascade="all, delete-orphan"
    )
    detections: Mapped[list["Detect"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Guardian(Base):
    __tablename__ = "guardians"
    __table_args__ = (
        UniqueConstraint("ward_user_id", "phone", name="uq_guardian_ward_phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ward_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(64))
    relation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ward: Mapped["User"] = relationship(back_populates="guardians")


class DetectionReport(Base):
    """检测报告表：一次检测的详细结论（JSON 字段在 PostgreSQL 中可用 JSONB）。"""

    __tablename__ = "report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detect_type: Mapped[str] = mapped_column(String(32), index=True)
    detect_content: Mapped[str] = mapped_column(Text, default="")
    overall_judgment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rag_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    multimodal_fusion_recognition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    personal_info_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fraud_type: Mapped[str] = mapped_column(String(512), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    detect_row: Mapped["Detect | None"] = relationship(
        back_populates="report",
        uselist=False,
    )


class Detect(Base):
    """检测记录表：每次调用 detect API 一条；关联 report。"""

    __tablename__ = "detect"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    isreport: Mapped[bool] = mapped_column("isreport", Boolean, default=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("report.id"), index=True)
    detect_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    risk_index: Mapped[float] = mapped_column(Float, default=0.0)
    detect_type: Mapped[str] = mapped_column(String(32), index=True)
    detect_content: Mapped[str] = mapped_column(Text, default="")

    user: Mapped["User"] = relationship(back_populates="detections")
    report: Mapped["DetectionReport"] = relationship(back_populates="detect_row")
