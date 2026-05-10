from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Project Management Archive System"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://project_mgmt:change-me@localhost:5432/project_mgmt"
    redis_url: str = "redis://localhost:6379/0"

    jwt_private_key_path: str = "/run/secrets/jwt_private_key.pem"
    jwt_public_key_path: str = "/run/secrets/jwt_public_key.pem"
    jwt_algorithm: str = "RS256"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    cors_allow_origins: str = "http://localhost:5173"
    rate_limit_per_minute: int = 100
    max_upload_size_mb: int = 50

    storage_backend: str = "local"
    storage_root: str = Field(default="/app/storage")
    storage_public_url_prefix: str = "/storage"
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = ""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
