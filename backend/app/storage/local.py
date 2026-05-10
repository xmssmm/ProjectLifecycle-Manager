from collections.abc import Callable
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from app.storage.base import StorageBackend, StorageSecurityError


class LocalStorageBackend(StorageBackend):
    def __init__(
        self,
        *,
        root: str | Path,
        public_url_prefix: str = "/storage",
        uuid_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._root = Path(root).resolve()
        self._public_url_prefix = public_url_prefix.rstrip("/")
        self._uuid_factory = uuid_factory
        self._root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        safe_sub_id = self._safe_segment(sub_id, "sub_id")
        safe_phase_id = self._safe_segment(phase_id, "phase_id")
        extension = self._safe_extension(filename)
        storage_key = PurePosixPath(
            safe_sub_id,
            safe_phase_id,
            f"{self._uuid_factory()}.{extension}",
        )
        absolute_path = self._resolve_key(storage_key.as_posix())
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)
        return storage_key.as_posix()

    def read(self, storage_key: str) -> bytes:
        return self._resolve_key(storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        self._resolve_key(storage_key).unlink(missing_ok=True)

    def get_url(self, storage_key: str) -> str:
        safe_key = self._safe_key(storage_key).as_posix()
        return f"{self._public_url_prefix}/{safe_key}"

    def _resolve_key(self, storage_key: str) -> Path:
        relative_path = self._safe_key(storage_key)
        absolute_path = (self._root / Path(*relative_path.parts)).resolve()
        try:
            absolute_path.relative_to(self._root)
        except ValueError as exc:
            raise StorageSecurityError("storage key escapes storage root") from exc
        return absolute_path

    @staticmethod
    def _safe_segment(value: str, field_name: str) -> str:
        if not value or "/" in value or "\\" in value or ".." in value:
            raise StorageSecurityError(f"{field_name} contains unsafe path characters")
        return value

    @staticmethod
    def _safe_extension(filename: str) -> str:
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            raise StorageSecurityError("filename contains unsafe path characters")

        suffix = Path(filename).suffix
        if not suffix:
            raise StorageSecurityError("filename must include an extension")
        return suffix.lstrip(".").lower()

    @staticmethod
    def _safe_key(storage_key: str) -> PurePosixPath:
        if not storage_key or "\\" in storage_key:
            raise StorageSecurityError("storage key contains unsafe path characters")

        relative_path = PurePosixPath(storage_key)
        if relative_path.is_absolute():
            raise StorageSecurityError("storage key must be relative")

        if any(part in {"", ".", ".."} or ".." in part for part in relative_path.parts):
            raise StorageSecurityError("storage key contains unsafe path characters")

        return relative_path
