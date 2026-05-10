from abc import ABC, abstractmethod


class StorageSecurityError(ValueError):
    pass


class StorageBackend(ABC):
    @abstractmethod
    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        pass

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        pass

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        pass

    @abstractmethod
    def get_url(self, storage_key: str) -> str:
        pass
