from app.core.config import Settings, get_settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend


def create_storage_backend(settings: Settings | None = None) -> StorageBackend:
    resolved_settings = settings or get_settings()
    backend = resolved_settings.storage_backend.lower()

    if backend == "local":
        return LocalStorageBackend(
            root=resolved_settings.storage_root,
            public_url_prefix=resolved_settings.storage_public_url_prefix,
        )

    if backend == "s3":
        return S3StorageBackend(
            bucket=resolved_settings.s3_bucket,
            endpoint_url=resolved_settings.s3_endpoint_url or None,
            access_key_id=resolved_settings.s3_access_key_id or None,
            secret_access_key=resolved_settings.s3_secret_access_key or None,
        )

    raise ValueError(f"Unsupported storage backend: {resolved_settings.storage_backend}")
