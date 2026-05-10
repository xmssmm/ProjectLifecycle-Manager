from __future__ import annotations

import enum
import socket
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.documents import Document, DocumentScanStatus
from app.models.users import User, UserRole, UserStatus
from app.services.notifications import NotificationService
from app.storage.base import StorageBackend

EICAR_TEST_CONTENT = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


class VirusScanStatus(enum.StrEnum):
    clean = "clean"
    infected = "infected"
    failed = "failed"


@dataclass(frozen=True)
class VirusScanResult:
    status: VirusScanStatus
    result: str


@dataclass(frozen=True)
class DocumentScanResult:
    document_id: UUID
    status: DocumentScanStatus
    result: str


class VirusScanner:
    def scan_bytes(self, *, file_name: str, content: bytes) -> VirusScanResult:
        raise NotImplementedError


class EicarSignatureVirusScanner(VirusScanner):
    def scan_bytes(self, *, file_name: str, content: bytes) -> VirusScanResult:
        _ = file_name
        if EICAR_TEST_CONTENT in content:
            return VirusScanResult(
                status=VirusScanStatus.infected,
                result="EICAR-Test-File FOUND",
            )
        return VirusScanResult(status=VirusScanStatus.clean, result="No threats found")


class ClamAvVirusScanner(VirusScanner):
    def __init__(self, *, host: str, port: int = 3310, timeout_seconds: float = 10.0) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds

    def scan_bytes(self, *, file_name: str, content: bytes) -> VirusScanResult:
        _ = file_name
        try:
            response = self._scan_with_clamd(content)
        except OSError as exc:
            return VirusScanResult(status=VirusScanStatus.failed, result=str(exc))

        normalized = response.strip()
        if normalized.endswith("OK"):
            return VirusScanResult(status=VirusScanStatus.clean, result=normalized)
        if "FOUND" in normalized:
            return VirusScanResult(status=VirusScanStatus.infected, result=normalized)
        return VirusScanResult(status=VirusScanStatus.failed, result=normalized or "Empty response")

    def _scan_with_clamd(self, content: bytes) -> str:
        with socket.create_connection(
            (self._host, self._port),
            timeout=self._timeout_seconds,
        ) as connection:
            connection.settimeout(self._timeout_seconds)
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 1024 * 1024):
                chunk = content[offset : offset + 1024 * 1024]
                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)
            connection.sendall(struct.pack("!I", 0))
            return connection.recv(4096).decode("utf-8", errors="replace")


class DocumentScanRepository:
    async def get_document_for_update(self, document_id: UUID) -> Document | None:
        raise NotImplementedError

    async def admin_user_ids(self) -> list[UUID]:
        raise NotImplementedError

    async def commit(self) -> None:
        raise NotImplementedError

    async def refresh(self, document: Document) -> None:
        raise NotImplementedError


class SqlAlchemyDocumentScanRepository(DocumentScanRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_document_for_update(self, document_id: UUID) -> Document | None:
        result = await self._session.scalar(
            select(Document).where(Document.id == document_id).with_for_update(),
        )
        return result if isinstance(result, Document) else None

    async def admin_user_ids(self) -> list[UUID]:
        result = await self._session.scalars(
            select(User.id).where(
                User.role == UserRole.admin,
                User.status == UserStatus.active,
            ),
        )
        return list(result.all())

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, document: Document) -> None:
        await self._session.refresh(document)


class InMemoryDocumentScanRepository(DocumentScanRepository):
    def __init__(
        self,
        *,
        documents: Sequence[Document] | None = None,
        admin_user_ids: Sequence[UUID] | None = None,
    ) -> None:
        self.documents = list(documents or [])
        self._admin_user_ids = list(admin_user_ids or [])

    async def get_document_for_update(self, document_id: UUID) -> Document | None:
        return next((document for document in self.documents if document.id == document_id), None)

    async def admin_user_ids(self) -> list[UUID]:
        return list(self._admin_user_ids)

    async def commit(self) -> None:
        return None

    async def refresh(self, document: Document) -> None:
        _ = document
        return None


class DocumentScanService:
    def __init__(
        self,
        *,
        repository: DocumentScanRepository,
        storage: StorageBackend,
        scanner: VirusScanner,
        notification_service: NotificationService | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner
        self._notification_service = notification_service
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def scan_document(self, document_id: UUID) -> DocumentScanResult:
        document = await self._repository.get_document_for_update(document_id)
        if document is None:
            raise ResourceNotFoundError("Document does not exist")

        try:
            virus_result = self._scanner.scan_bytes(
                file_name=document.file_name,
                content=self._storage.read(document.file_path),
            )
        except Exception as exc:  # noqa: BLE001
            virus_result = VirusScanResult(status=VirusScanStatus.failed, result=str(exc))

        status = self._document_status(virus_result.status)
        now = self._now_provider()
        document.scan_status = status
        document.scan_result = virus_result.result
        document.scanned_at = now
        document.updated_at = now
        await self._repository.commit()
        await self._repository.refresh(document)

        if status == DocumentScanStatus.infected and self._notification_service is not None:
            await self._notify_infected(document)

        return DocumentScanResult(
            document_id=document.id,
            status=status,
            result=virus_result.result,
        )

    async def _notify_infected(self, document: Document) -> None:
        if self._notification_service is None:
            return
        admin_user_ids = await self._repository.admin_user_ids()
        receivers = list(dict.fromkeys([document.uploader_id, *admin_user_ids]))
        await self._notification_service.send(
            scenario="document_infected",
            receivers=receivers,
            source_id=document.id,
            payload={
                "document_id": str(document.id),
                "file_name": document.file_name,
                "doc_type": document.doc_type,
                "scan_result": document.scan_result or "",
            },
        )

    @staticmethod
    def _document_status(status: VirusScanStatus) -> DocumentScanStatus:
        if status == VirusScanStatus.clean:
            return DocumentScanStatus.clean
        if status == VirusScanStatus.infected:
            return DocumentScanStatus.infected
        return DocumentScanStatus.failed
