from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

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

    monitor_guardians: Mapped[list["Guardian"]] = orm_relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        foreign_keys="Guardian.monitor_id",
    )
    ward_guardians: Mapped[list["Guardian"]] = orm_relationship(
        back_populates="ward",
        cascade="all, delete-orphan",
        foreign_keys="Guardian.ward_id",
    )
    outgoing_guardian_requests: Mapped[list["GuardianLinkRequest"]] = orm_relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        foreign_keys="GuardianLinkRequest.monitor_id",
    )
    incoming_guardian_requests: Mapped[list["GuardianLinkRequest"]] = orm_relationship(
        back_populates="ward",
        cascade="all, delete-orphan",
        foreign_keys="GuardianLinkRequest.ward_id",
    )
    detections: Mapped[list["Detect"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped["UserProfile | None"] = orm_relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profile_user"),
        UniqueConstraint("phone", name="uq_user_profile_phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    phone: Mapped[str] = mapped_column(String(32))
    birth_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    occupation_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occupation_subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region_province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region_city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = orm_relationship(back_populates="profile")


class Guardian(Base):
    __tablename__ = "guardians"
    __table_args__ = (
        UniqueConstraint("monitor_id", "ward_id", name="uq_guardian_monitor_ward"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    monitor_note: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ward_note: Mapped[str | None] = mapped_column(String(64), nullable=True)
    relationship: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    monitor: Mapped["User"] = orm_relationship(
        back_populates="monitor_guardians",
        foreign_keys=[monitor_id],
    )
    ward: Mapped["User"] = orm_relationship(
        back_populates="ward_guardians",
        foreign_keys=[ward_id],
    )


class GuardianLinkRequest(Base):
    __tablename__ = "guardian_link_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    relationship: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    monitor: Mapped["User"] = orm_relationship(
        back_populates="outgoing_guardian_requests",
        foreign_keys=[monitor_id],
    )
    ward: Mapped["User"] = orm_relationship(
        back_populates="incoming_guardian_requests",
        foreign_keys=[ward_id],
    )


class DetectionReport(Base):
    """检测报告表：一次检测的详细结论（JSON 字段在 PostgreSQL 中可用 JSONB）。"""

    __tablename__ = "report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detect_type: Mapped[str] = mapped_column(String(32), index=True)
    detect_content: Mapped[str] = mapped_column(Text, default="")
    source_materials: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    overall_judgment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rag_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    multimodal_fusion_recognition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    personal_info_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fraud_type: Mapped[str] = mapped_column(String(512), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    detect_row: Mapped["Detect | None"] = orm_relationship(
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

    user: Mapped["User"] = orm_relationship(back_populates="detections")
    report: Mapped["DetectionReport"] = orm_relationship(back_populates="detect_row")


class AgentChatSession(Base):
    __tablename__ = "agent_chat_sessions"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_agent_chat_user_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    mode: Mapped[str] = mapped_column(String(16), default="chat", index=True)
    detect_stage: Mapped[str] = mapped_column(String(32), default="guide", index=True)
    candidate_content: Mapped[str] = mapped_column(Text, default="")
    candidate_materials: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AgentChatMessage(Base):
    __tablename__ = "agent_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey("agent_chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
