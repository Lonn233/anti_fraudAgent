from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "anti-fraud-agent-backend"
    env: Literal["dev", "prod", "test"] = "dev"

    database_url: str = "sqlite:///./data/app.db"

    jwt_secret_key: str = "change_me_to_a_long_random_secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    storage_dir: str = "./storage"
    max_upload_mb: int = 50
    # 对外访问本服务资源时用于拼接完整 URL（数据库存相对路径 /media/...）
    public_base_url: str = "http://127.0.0.1:8010"

    # 豆包 / 火山方舟向量化（OpenAI 兼容 POST {base}/embeddings）
    doubao_ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_api_key: str = ""
    doubao_embedding_model: str = "doubao-embedding-vision-251215"
    # 对话（文本与带图/带视频请求共用同一端点模型 ID）
    doubao_chat_model: str = "doubao-seed-2-0-mini-260215"
    # 语音识别（OpenAI 兼容音频转写端点）
    doubao_asr_model: str = "doubao-seed-asr-1-0"
    # 语音识别（OpenSpeech 大模型录音识别提交接口）
    doubao_asr_submit_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
    doubao_asr_resource_id: str = "volc.seedasr.auc"
    doubao_asr_api_key: str = ""
    # 可选：本地/内网 ASR 微服务（配置后优先使用）
    asr_service_base_url: str = ""
    asr_service_timeout_sec: int = 180

    # Milvus（Docker 部署）
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: str = ""
    milvus_collection: str = "anti_fraud_text_kb"
    milvus_embedding_dim: int = 2048

    # 知识库文本分段（字符级，粗略适合中英混排）
    kb_chunk_max_chars: int = 500
    kb_chunk_overlap_chars: int = 80

    # 多模态深度学习检测（MVP）
    model_detect_device: str = "cuda"
    model_detect_fraud_labels: str = "刷单诈骗,虚假征信诈骗,贷款诈骗,投资理财诈骗,冒充客服诈骗"
    model_detect_text_cls_model: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    model_detect_ai_voice_model: str = ""
    model_detect_asr_model: str = "large-v3"
    model_detect_ocr_lang: str = "ch"
    model_detect_max_video_frames: int = 3

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()


settings = Settings()
