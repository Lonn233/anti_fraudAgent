from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    age: int | None = None
    job: str | None = None
    region: str | None = None
    created_at: datetime


class UserProfileIn(BaseModel):
    age: int | None = Field(default=None, ge=0, le=150)
    job: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)


class GuardianCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    relation: str | None = Field(default=None, max_length=64)
    phone: str = Field(min_length=5, max_length=32)


class GuardianOut(BaseModel):
    id: int
    name: str
    relation: str | None
    phone: str
    created_at: datetime


class DetectTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class DetectOut(BaseModel):
    id: int
    kind: Literal["text", "image", "audio", "video"]
    risk_score: int
    reasons: list[str]
    created_at: datetime


class TextKbUploadIn(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
    doc_id: str | None = Field(default=None, max_length=128)
    chunk_max_chars: int | None = Field(default=None, ge=200, le=4000)
    chunk_overlap_chars: int | None = Field(default=None, ge=0, le=2000)
    # 可选字段：用户信息和诈骗案例信息
    age: int | None = Field(default=None, ge=0, le=150)
    job: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    fraud_type: str | None = Field(default=None, max_length=128)
    fraud_amount: float | None = Field(default=None, ge=0)


class TextKbUploadOut(BaseModel):
    doc_id: str
    chunk_count: int
    inserted: int
    milvus_collection: str
    embedding_model: str


class TextReportIn(BaseModel):
    """单个诈骗案例上报（不分段）"""
    text: str = Field(min_length=1, max_length=500_000)
    doc_id: str | None = Field(default=None, max_length=128)
    age: int | None = Field(default=None, ge=0, le=150)
    job: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    fraud_type: str | None = Field(default=None, max_length=128)
    fraud_amount: float | None = Field(default=None, ge=0)


class TextReportOut(BaseModel):
    """单个案例上报响应"""
    doc_id: str
    inserted: int
    milvus_collection: str
    embedding_model: str


class TextUploadIn(BaseModel):
    """批量文本上传（自动分段）"""
    text: str = Field(min_length=1, max_length=500_000)
    doc_id: str | None = Field(default=None, max_length=128)


class TextUploadOut(BaseModel):
    """批量文本上传响应"""
    doc_id: str
    chunk_count: int
    inserted: int
    milvus_collection: str
    embedding_model: str
