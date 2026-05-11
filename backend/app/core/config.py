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
    database_replica_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    redis_sentinel_enabled: bool = False
    redis_sentinel_hosts: str = ""
    redis_sentinel_master_name: str = "mymaster"
    redis_sentinel_db: int = 0
    redis_sentinel_password: str = ""
    redis_sentinel_socket_timeout_seconds: float = 1.0
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    jwt_private_key_path: str = "/run/secrets/jwt_private_key.pem"
    jwt_public_key_path: str = "/run/secrets/jwt_public_key.pem"
    jwt_algorithm: str = "RS256"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_per_minute: int = 100
    max_upload_size_mb: int = 50

    oauth_generic_enabled: bool = False
    oauth_generic_label: str = "企业账号"
    oauth_generic_client_id: str = ""
    oauth_generic_client_secret: str = ""
    oauth_generic_authorize_url: str = ""
    oauth_generic_token_url: str = ""
    oauth_generic_userinfo_url: str = ""
    oauth_generic_redirect_uri: str = ""
    oauth_generic_bind_redirect_uri: str = ""
    oauth_generic_scope: str = "openid email profile"

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True

    wework_enabled: bool = False
    wework_webhook_url: str = ""
    wework_webhook_secret: str = ""

    dingtalk_enabled: bool = False
    dingtalk_webhook_url: str = ""
    dingtalk_webhook_secret: str = ""

    storage_backend: str = "local"
    storage_root: str = Field(default="/app/storage")
    storage_public_url_prefix: str = "/storage"
    report_async_threshold_rows: int = 1000
    office_preview_converter_binary: str = "libreoffice"
    office_preview_conversion_timeout_seconds: int = 30
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 10.0
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

    @property
    def effective_read_database_url(self) -> str:
        return self.database_replica_url or self.database_url

    @property
    def redis_sentinel_host_tuples(self) -> list[tuple[str, int]]:
        hosts: list[tuple[str, int]] = []
        for raw_host in self.redis_sentinel_hosts.split(","):
            host = raw_host.strip()
            if not host:
                continue
            name, separator, port = host.rpartition(":")
            if not separator or not name or not port:
                raise ValueError("Redis Sentinel hosts must use host:port entries")
            hosts.append((name, int(port)))
        return hosts

    @property
    def effective_redis_sentinel_url(self) -> str:
        return ";".join(
            f"sentinel://{host}:{port}" for host, port in self.redis_sentinel_host_tuples
        )

    @property
    def celery_sentinel_transport_options(self) -> dict[str, object]:
        if not self.redis_sentinel_enabled:
            return {}
        options: dict[str, object] = {
            "master_name": self.redis_sentinel_master_name,
            "db": self.redis_sentinel_db,
        }
        if self.redis_sentinel_password:
            options["password"] = self.redis_sentinel_password
            options["sentinel_kwargs"] = {"password": self.redis_sentinel_password}
        return options

    @property
    def effective_celery_broker_url(self) -> str:
        if self.celery_broker_url:
            return self.celery_broker_url
        if self.redis_sentinel_enabled and self.redis_sentinel_host_tuples:
            return self.effective_redis_sentinel_url
        return self.redis_url

    @property
    def effective_celery_result_backend(self) -> str:
        if self.celery_result_backend:
            return self.celery_result_backend
        if self.redis_sentinel_enabled and self.redis_sentinel_host_tuples:
            return self.effective_redis_sentinel_url
        return self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
