from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document
from app.storage.local import LocalStorageBackend


@dataclass(frozen=True)
class StorageFile:
    storage_key: str
    modified_at: datetime


@dataclass(frozen=True)
class FileCleanupResult:
    dry_run: bool
    scanned_files: int
    orphan_files: list[str]
    soft_deleted_files: list[str]
    deleted_files: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "scanned_files": self.scanned_files,
            "orphan_files": self.orphan_files,
            "soft_deleted_files": self.soft_deleted_files,
            "deleted_files": self.deleted_files,
        }


class FileCleanupRepository(Protocol):
    async def list_referenced_file_paths(self) -> set[str]:
        ...

    async def list_soft_deleted_documents(self, cutoff: datetime) -> list[Document]:
        ...


class StorageCleanupBackend(Protocol):
    def list_files(self) -> list[StorageFile]:
        ...

    def delete(self, storage_key: str) -> None:
        ...


class CleanupLogger(Protocol):
    def info(self, event: str, **kwargs: object) -> None:
        ...


class SqlAlchemyFileCleanupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_referenced_file_paths(self) -> set[str]:
        result = await self._session.scalars(select(Document.file_path))
        return set(result.all())

    async def list_soft_deleted_documents(self, cutoff: datetime) -> list[Document]:
        result = await self._session.scalars(
            select(Document).where(
                Document.is_deleted.is_(True),
                Document.updated_at <= cutoff,
            ),
        )
        return list(result.all())


class InMemoryFileCleanupRepository:
    def __init__(self, *, documents: Sequence[Document]) -> None:
        self.documents = list(documents)

    async def list_referenced_file_paths(self) -> set[str]:
        return {document.file_path for document in self.documents}

    async def list_soft_deleted_documents(self, cutoff: datetime) -> list[Document]:
        return [
            document
            for document in self.documents
            if document.is_deleted and document.updated_at <= cutoff
        ]


class LocalStorageCleanupBackend:
    def __init__(self, *, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._storage = LocalStorageBackend(root=self._root)

    def list_files(self) -> list[StorageFile]:
        files: list[StorageFile] = []
        for path in self._root.rglob("*"):
            if not path.is_file():
                continue
            storage_key = path.relative_to(self._root).as_posix()
            files.append(
                StorageFile(
                    storage_key=storage_key,
                    modified_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
                ),
            )
        return sorted(files, key=lambda item: item.storage_key)

    def delete(self, storage_key: str) -> None:
        self._storage.delete(storage_key)


class InMemoryStorageCleanupBackend:
    def __init__(self, *, files: Sequence[StorageFile]) -> None:
        self._files = {file.storage_key: file for file in files}
        self.deleted_keys: list[str] = []

    @property
    def remaining_keys(self) -> list[str]:
        return sorted(self._files)

    def list_files(self) -> list[StorageFile]:
        return sorted(self._files.values(), key=lambda item: item.storage_key)

    def delete(self, storage_key: str) -> None:
        self.deleted_keys.append(storage_key)
        self._files.pop(storage_key, None)


class FileCleanupService:
    def __init__(
        self,
        *,
        repository: FileCleanupRepository,
        storage: StorageCleanupBackend,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
        logger: CleanupLogger | None = None,
        orphan_retention: timedelta = timedelta(days=7),
        soft_deleted_retention: timedelta = timedelta(days=90),
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._now_provider = now_provider
        self._logger = logger or cast(CleanupLogger, structlog.get_logger("app.file_cleanup"))
        self._orphan_retention = orphan_retention
        self._soft_deleted_retention = soft_deleted_retention

    async def cleanup(self, *, dry_run: bool) -> FileCleanupResult:
        now = self._now_provider()
        orphan_cutoff = now - self._orphan_retention
        soft_deleted_cutoff = now - self._soft_deleted_retention
        storage_files = self._storage.list_files()
        referenced_file_paths = await self._repository.list_referenced_file_paths()
        soft_deleted_documents = await self._repository.list_soft_deleted_documents(
            soft_deleted_cutoff,
        )

        orphan_files = sorted(
            file.storage_key
            for file in storage_files
            if file.modified_at <= orphan_cutoff and file.storage_key not in referenced_file_paths
        )
        soft_deleted_files = sorted({document.file_path for document in soft_deleted_documents})
        delete_targets = sorted(set(orphan_files) | set(soft_deleted_files))

        deleted_files: list[str] = []
        if not dry_run:
            for storage_key in delete_targets:
                self._storage.delete(storage_key)
                deleted_files.append(storage_key)

        result = FileCleanupResult(
            dry_run=dry_run,
            scanned_files=len(storage_files),
            orphan_files=orphan_files,
            soft_deleted_files=soft_deleted_files,
            deleted_files=deleted_files,
        )
        self._logger.info(
            "file_cleanup.completed",
            dry_run=result.dry_run,
            scanned_files=result.scanned_files,
            orphan_files=len(result.orphan_files),
            soft_deleted_files=len(result.soft_deleted_files),
            deleted_files=len(result.deleted_files),
        )
        return result
