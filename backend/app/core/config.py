from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "intelligent-customer-service-agent"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me-in-local-env"
    readiness_strict: bool = False
    jwt_access_expires_seconds: int = 900
    jwt_refresh_expires_seconds: int = 604800
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_cookie_domain: str | None = None

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/customer_service"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"
    rustfs_endpoint: str = "http://localhost:9000"
    rustfs_access_key: str = "rustfsadmin"
    rustfs_secret_key: str = "rustfsadmin"
    rustfs_bucket: str = "customer-service"
    mineru_api_key: str = ""
    mineru_base_url: str = "https://mineru.net"
    mineru_model_version: str = "vlm"
    mineru_language: str = "ch"
    mineru_enable_formula: bool = True
    mineru_enable_table: bool = True
    mineru_poll_interval_ms: int = 3000
    mineru_poll_timeout_ms: int = 600000
    embedding_api_key: str = ""
    embedding_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    embedding_model: str = "qwen3.7-text-embedding"
    embedding_dimension: int = 1024
    rerank_enabled: bool = True
    rerank_api_key: str = ""
    rerank_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    rerank_model: str = "qwen3.7-text-rerank"
    rerank_max_documents: int = 50
    rerank_max_document_chars: int = 8000

    cors_origins: str = "http://localhost:5173,http://localhost:55173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
