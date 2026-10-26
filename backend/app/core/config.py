from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "intelligent-customer-service-agent"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me-in-local-env"
    readiness_strict: bool = False

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/customer_service"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    milvus_uri: str = "http://localhost:19530"
    neo4j_uri: str = "bolt://localhost:7687"
    rustfs_endpoint: str = "http://localhost:9000"

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
