from app.storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        raise NotImplementedError("S3 storage save is not implemented yet.")

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError("S3 storage read is not implemented yet.")

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError("S3 storage delete is not implemented yet.")

    def get_url(self, storage_key: str) -> str:
        raise NotImplementedError("S3 storage URL generation is not implemented yet.")
