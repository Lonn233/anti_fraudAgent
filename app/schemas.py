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
    phone: str = Field(min_length=5, max_length=32)
    birth_date: str | None = Field(default=None, max_length=16)
    occupation_category: str | None = Field(default=None, max_length=64)
    occupation_subcategory: str | None = Field(default=None, max_length=64)
    region_province: str | None = Field(default=None, max_length=64)
    region_city: str | None = Field(default=None, max_length=64)


class RegisterCheckIn(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    phone: str | None = Field(default=None, min_length=5, max_length=32)


class RegisterCheckOut(BaseModel):
    username_exists: bool = False
    phone_exists: bool = False


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    phone: str | None = None
    birth_date: str | None = None
    occupation_category: str | None = None
    occupation_subcategory: str | None = None
    region_province: str | None = None
    region_city: str | None = None
    age: int | None = None
    job: str | None = None
    region: str | None = None
    created_at: datetime


class UserProfileIn(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    birth_date: str | None = Field(default=None, max_length=16)
    occupation_category: str | None = Field(default=None, max_length=64)
    occupation_subcategory: str | None = Field(default=None, max_length=64)
    region_province: str | None = Field(default=None, max_length=64)
    region_city: str | None = Field(default=None, max_length=64)
    age: int | None = Field(default=None, ge=0, le=150)
    job: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class GuardianOut(BaseModel):
    id: int
    monitor_id: int
    monitor_username: str | None = None
    monitor_phone: str | None = None
    ward_id: int
    ward_username: str | None = None
    ward_phone: str | None = None
    monitor_note: str | None = None
    ward_note: str | None = None
    note: str | None = None
    phone: str | None = None
    relationship: str | None
    created_at: datetime


class GuardianPageOut(BaseModel):
    items: list[GuardianOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class GuardianUpdateIn(BaseModel):
    note: str | None = Field(default=None, max_length=64)


class GuardianRequestOut(BaseModel):
    id: int
    monitor_id: int
    monitor_username: str
    ward_id: int
    ward_username: str
    name: str
    relationship: str | None
    status: str
    created_at: datetime
    processed_at: datetime | None = None


class GuardianRequestApplyIn(BaseModel):
    mode: Literal["monitor", "ward"]
    target_username: str = Field(max_length=64)
    name: str = Field(max_length=64)
    relationship: str | None = Field(default=None, max_length=64)


class GuardianRequestDecisionIn(BaseModel):
    decision: Literal["accept", "reject"]
    note: str | None = Field(default=None, max_length=64)


class GuardianRequestDecisionOut(BaseModel):
    request: GuardianRequestOut
    guardian: GuardianOut | None = None


class DetectTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class AgentChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20000)


class AgentChatOut(BaseModel):
    mode: Literal["chat"] = "chat"
    reply: str
    suggested_mode: Literal["none", "detect", "alert"] = "none"


class AgentDetectMaterialIn(BaseModel):
    type: Literal["text", "image", "video", "audio"]
    content: str | None = Field(default=None, max_length=20000)
    url: str | None = Field(default=None, max_length=2048)
    summary_text: str | None = Field(default=None, max_length=20000)
    file_name: str | None = Field(default=None, max_length=255)


class AgentDetectMaterialOut(BaseModel):
    type: Literal["text", "image", "video", "audio"]
    content: str | None = None
    url: str | None = None
    summary_text: str | None = None
    file_name: str | None = None


class AgentDetectOut(BaseModel):
    mode: Literal["detect"] = "detect"
    reply: str
    detect_stage: Literal["guide", "awaiting_confirm"] = "guide"
    candidate_content: str = ""
    candidate_materials: list[AgentDetectMaterialOut] = Field(default_factory=list)
    should_run_detect: bool = False
    detect_result: DetectOut | None = None


class AgentChatSessionOut(BaseModel):
    session_id: str
    updated_at: datetime
    message_count: int = 0


class AgentChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime


class AgentDetectIn(BaseModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    text: str = Field(default="", max_length=20000)
    materials: list[AgentDetectMaterialIn] = Field(default_factory=list)


class AgentAlertIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    notify: bool = True


class AgentSpeechTranscribeOut(BaseModel):
    text: str


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


class ModelDetectFraudOut(BaseModel):
    labels: dict[str, float] = Field(default_factory=dict)
    top_label: str = ""
    top_score: float = 0.0


class ModelDetectAiVoiceOut(BaseModel):
    probability: float | None = None
    judgment: str = ""
    evidence: str = ""


class ModelDetectOut(BaseModel):
    media_type: str
    extracted_text: str = ""
    fraud_classification: ModelDetectFraudOut
    ai_voice_detection: ModelDetectAiVoiceOut
    ocr_text: str = ""
    asr_text: str = ""
    notes: list[str] = Field(default_factory=list)
