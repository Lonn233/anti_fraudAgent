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

    # 豆包 / 火山方舟向量化（OpenAI 兼容 POST {base}/embeddings）
    doubao_ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_api_key: str = ""
    doubao_embedding_model: str = "doubao-embedding-vision-251215"
    # 对话（文本与带图/带视频请求共用同一端点模型 ID）
    doubao_chat_model: str = "doubao-seed-2-0-mini-260215"

    # Milvus（Docker 部署）
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: str = ""
    milvus_collection: str = "anti_fraud_text_kb"
    milvus_embedding_dim: int = 2048

    # 知识库文本分段（字符级，粗略适合中英混排）
    kb_chunk_max_chars: int = 500
    kb_chunk_overlap_chars: int = 80

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()


settings = Settings()
