from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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


class DetectMetaDataOut(BaseModel):
    report_id: str = ""
    detect_type: str = ""
    detect_content: str = ""
    detect_time: str = ""


class DetectOverallJudgmentOut(BaseModel):
    risk_index: float | None = None
    fraud_type_rag: str = ""
    conclusion: str = ""
    prevention_measures: str = ""
    post_fraud_actions: str = ""


class DetectRagResultOut(BaseModel):
    retrieved_case: str = ""
    similarity: float | None = None
    retrieval_reason: str = ""


class DetectMultimodalFusionRecognitionOut(BaseModel):
    ai_synthesis_probability: float | None = None
    judgment_reason: str = ""


class DetectPersonalInfoAnalysisOut(BaseModel):
    conclusion: str = ""


class DetectReportContentOut(BaseModel):
    meta_data: DetectMetaDataOut
    overall_judgment: DetectOverallJudgmentOut
    rag_result: DetectRagResultOut
    multimodal_fusion_recognition: DetectMultimodalFusionRecognitionOut
    personal_info_analysis: DetectPersonalInfoAnalysisOut


class DetectOut(BaseModel):
    risk_index: float
    isReport: bool
    report_content: DetectReportContentOut


class TextKbUploadIn(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
    doc_id: str | None = Field(default=None, max_length=128)
    chunk_max_chars: int | None = Field(default=None, ge=200, le=4000)
    chunk_overlap_chars: int | None = Field(default=None, ge=0, le=2000)
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
    text: str = Field(min_length=1, max_length=500_000)
    doc_id: str | None = Field(default=None, max_length=128)
    age: int | None = Field(default=None, ge=0, le=150)
    job: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    fraud_type: str | None = Field(default=None, max_length=128)
    fraud_amount: float | None = Field(default=None, ge=0)


class TextReportOut(BaseModel):
    doc_id: str
    inserted: int
    milvus_collection: str
    embedding_model: str


class TextUploadIn(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
    doc_id: str | None = Field(default=None, max_length=128)


class TextUploadOut(BaseModel):
    doc_id: str
    chunk_count: int
    inserted: int
    milvus_collection: str
    embedding_model: str
