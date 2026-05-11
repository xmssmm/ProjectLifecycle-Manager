from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, ValidationFailedError
from app.models.documents import Document, DocumentScanStatus
from app.models.phases import Phase
from app.models.search import DocumentSearchEntry, DocumentSearchStatus
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.users import User, UserRole
from app.services.document_text_extraction import DocumentTextExtractor
from app.storage.base import StorageBackend

SEARCH_VIEW_ALL_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)


@dataclass(frozen=True)
class DocumentIndexResult:
    document_id: UUID
    status: DocumentSearchStatus
    error_message: str | None = None


@dataclass(frozen=True)
class DocumentSearchRecord:
    entry: DocumentSearchEntry
    document: Document
    sub_project: SubProject
    phase: Phase


@dataclass(frozen=True)
class DocumentSearchResult:
    document_id: UUID
    file_name: str
    doc_type: str
    sub_project_id: UUID
    sub_project_no: str
    sub_project_name: str
    phase_id: UUID
    phase_name: str
    snippet: str


@dataclass(frozen=True)
class DocumentSearchResults:
    items: list[DocumentSearchResult]
    total: int


class DocumentSearchRepository(Protocol):
    async def get_document(self, document_id: UUID) -> Document | None:
        ...

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def upsert_entry(
        self,
        *,
        document: Document,
        content_text: str,
        status: DocumentSearchStatus,
        error_message: str | None,
        indexed_at: datetime | None,
    ) -> DocumentSearchEntry:
        ...

    async def delete_entry_for_document(self, document_id: UUID) -> None:
        ...

    async def search_entries(
        self,
        *,
        actor: User,
        query: str,
        limit: int,
    ) -> list[DocumentSearchRecord]:
        ...

    async def commit(self) -> None:
        ...


class SqlAlchemyDocumentSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_document(self, document_id: UUID) -> Document | None:
        document = await self._session.get(Document, document_id)
        return document if isinstance(document, Document) else None

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.get(SubProject, sub_project_id)
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        phase = await self._session.get(Phase, phase_id)
        return phase if isinstance(phase, Phase) else None

    async def upsert_entry(
        self,
        *,
        document: Document,
        content_text: str,
        status: DocumentSearchStatus,
        error_message: str | None,
        indexed_at: datetime | None,
    ) -> DocumentSearchEntry:
        entry = await self._session.scalar(
            select(DocumentSearchEntry).where(DocumentSearchEntry.document_id == document.id),
        )
        if not isinstance(entry, DocumentSearchEntry):
            entry = DocumentSearchEntry(
                id=uuid4(),
                document_id=document.id,
                sub_project_id=document.sub_project_id,
                phase_id=document.phase_id,
                file_name=document.file_name,
                doc_type=document.doc_type,
                content_text="",
                status=status,
                created_at=indexed_at or datetime.now(UTC),
                updated_at=indexed_at or datetime.now(UTC),
            )
            self._session.add(entry)

        entry.sub_project_id = document.sub_project_id
        entry.phase_id = document.phase_id
        entry.file_name = document.file_name
        entry.doc_type = document.doc_type
        entry.content_text = content_text
        entry.status = status
        entry.error_message = error_message
        entry.indexed_at = indexed_at
        entry.updated_at = indexed_at or datetime.now(UTC)
        entry.search_vector = (
            func.to_tsvector("simple", self._combined_search_text(document, content_text))
            if status == DocumentSearchStatus.indexed
            else None
        )
        return entry

    async def delete_entry_for_document(self, document_id: UUID) -> None:
        await self._session.execute(
            delete(DocumentSearchEntry).where(DocumentSearchEntry.document_id == document_id),
        )

    async def search_entries(
        self,
        *,
        actor: User,
        query: str,
        limit: int,
    ) -> list[DocumentSearchRecord]:
        ts_query = func.plainto_tsquery("simple", query)
        conditions = [
            DocumentSearchEntry.status == DocumentSearchStatus.indexed,
            Document.is_deleted.is_(False),
            Document.scan_status == DocumentScanStatus.clean,
            DocumentSearchEntry.search_vector.op("@@")(ts_query),
        ]
        if actor.role not in SEARCH_VIEW_ALL_ROLES:
            member_exists = exists().where(
                SubProjectMember.sub_project_id == SubProject.id,
                SubProjectMember.user_id == actor.id,
            )
            conditions.append(or_(SubProject.manager_id == actor.id, member_exists))

        result = await self._session.execute(
            select(DocumentSearchEntry, Document, SubProject, Phase)
            .join(Document, Document.id == DocumentSearchEntry.document_id)
            .join(SubProject, SubProject.id == DocumentSearchEntry.sub_project_id)
            .join(Phase, Phase.id == DocumentSearchEntry.phase_id)
            .where(*conditions)
            .order_by(func.ts_rank(DocumentSearchEntry.search_vector, ts_query).desc())
            .limit(limit),
        )
        return [
            DocumentSearchRecord(
                entry=entry,
                document=document,
                sub_project=sub_project,
                phase=phase,
            )
            for entry, document, sub_project, phase in result.all()
        ]

    async def commit(self) -> None:
        await self._session.commit()

    @staticmethod
    def _combined_search_text(document: Document, content_text: str) -> str:
        return "\n".join([document.file_name, document.doc_type, content_text])


class InMemoryDocumentSearchRepository:
    def __init__(
        self,
        *,
        documents: Sequence[Document] | None = None,
        phases: Sequence[Phase] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
    ) -> None:
        self.documents = list(documents or [])
        self.phases = list(phases or [])
        self.sub_projects = list(sub_projects or [])
        self.entries: list[DocumentSearchEntry] = []

    async def get_document(self, document_id: UUID) -> Document | None:
        return next((document for document in self.documents if document.id == document_id), None)

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        return next((phase for phase in self.phases if phase.id == phase_id), None)

    async def upsert_entry(
        self,
        *,
        document: Document,
        content_text: str,
        status: DocumentSearchStatus,
        error_message: str | None,
        indexed_at: datetime | None,
    ) -> DocumentSearchEntry:
        entry = next((item for item in self.entries if item.document_id == document.id), None)
        if entry is None:
            now = indexed_at or datetime.now(UTC)
            entry = DocumentSearchEntry(
                id=uuid4(),
                document_id=document.id,
                sub_project_id=document.sub_project_id,
                phase_id=document.phase_id,
                file_name=document.file_name,
                doc_type=document.doc_type,
                content_text="",
                status=status,
                created_at=now,
                updated_at=now,
            )
            self.entries.append(entry)

        entry.sub_project_id = document.sub_project_id
        entry.phase_id = document.phase_id
        entry.file_name = document.file_name
        entry.doc_type = document.doc_type
        entry.content_text = content_text
        entry.status = status
        entry.error_message = error_message
        entry.indexed_at = indexed_at
        entry.updated_at = indexed_at or datetime.now(UTC)
        return entry

    async def delete_entry_for_document(self, document_id: UUID) -> None:
        self.entries = [entry for entry in self.entries if entry.document_id != document_id]

    async def search_entries(
        self,
        *,
        actor: User,
        query: str,
        limit: int,
    ) -> list[DocumentSearchRecord]:
        needle = query.casefold()
        records: list[DocumentSearchRecord] = []
        for entry in self.entries:
            document = await self.get_document(entry.document_id)
            sub_project = await self.get_sub_project(entry.sub_project_id)
            phase = await self.get_phase(entry.phase_id)
            if document is None or sub_project is None or phase is None:
                continue
            if not self._can_actor_see(actor, sub_project):
                continue
            if entry.status != DocumentSearchStatus.indexed:
                continue
            if document.is_deleted or document.scan_status != DocumentScanStatus.clean:
                continue
            haystack = "\n".join([entry.file_name, entry.doc_type, entry.content_text]).casefold()
            if needle not in haystack:
                continue
            records.append(
                DocumentSearchRecord(
                    entry=entry,
                    document=document,
                    sub_project=sub_project,
                    phase=phase,
                ),
            )
        return records[:limit]

    async def commit(self) -> None:
        return None

    @staticmethod
    def _can_actor_see(actor: User, sub_project: SubProject) -> bool:
        return actor.role in SEARCH_VIEW_ALL_ROLES or sub_project.manager_id == actor.id


class DocumentSearchService:
    def __init__(
        self,
        *,
        repository: DocumentSearchRepository,
        storage: StorageBackend,
        text_extractor: DocumentTextExtractor | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._text_extractor = text_extractor or DocumentTextExtractor()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def index_document(self, document_id: UUID) -> DocumentIndexResult:
        document = await self._repository.get_document(document_id)
        if document is None:
            raise ResourceNotFoundError("文档不存在")

        if document.is_deleted or document.scan_status != DocumentScanStatus.clean:
            await self._repository.delete_entry_for_document(document.id)
            await self._repository.commit()
            return DocumentIndexResult(
                document_id=document.id,
                status=DocumentSearchStatus.skipped,
            )

        indexed_at = self._now_provider()
        try:
            content_text = self._text_extractor.extract_text(
                file_name=document.file_name,
                content=self._storage.read(document.file_path),
            )
        except Exception as exc:  # noqa: BLE001
            await self._repository.upsert_entry(
                document=document,
                content_text="",
                status=DocumentSearchStatus.failed,
                error_message=str(exc),
                indexed_at=indexed_at,
            )
            await self._repository.commit()
            return DocumentIndexResult(
                document_id=document.id,
                status=DocumentSearchStatus.failed,
                error_message=str(exc),
            )

        await self._repository.upsert_entry(
            document=document,
            content_text=content_text,
            status=DocumentSearchStatus.indexed,
            error_message=None,
            indexed_at=indexed_at,
        )
        await self._repository.commit()
        return DocumentIndexResult(document_id=document.id, status=DocumentSearchStatus.indexed)

    async def search_documents(
        self,
        *,
        actor: User,
        query: str,
        scope: str = "documents",
        limit: int = 20,
    ) -> DocumentSearchResults:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValidationFailedError("搜索关键词不能为空")
        if scope != "documents":
            raise ValidationFailedError("暂不支持的搜索范围", data={"scope": scope})

        records = await self._repository.search_entries(
            actor=actor,
            query=cleaned_query,
            limit=limit,
        )
        items = [
            DocumentSearchResult(
                document_id=record.document.id,
                file_name=record.document.file_name,
                doc_type=record.document.doc_type,
                sub_project_id=record.sub_project.id,
                sub_project_no=record.sub_project.project_no,
                sub_project_name=record.sub_project.name,
                phase_id=record.phase.id,
                phase_name=record.phase.name,
                snippet=self._snippet(record.entry.content_text, cleaned_query),
            )
            for record in records
        ]
        return DocumentSearchResults(items=items, total=len(items))

    @staticmethod
    def _snippet(content: str, query: str, *, radius: int = 80) -> str:
        if not content:
            return ""
        index = content.casefold().find(query.casefold())
        if index < 0:
            return content[: radius * 2]
        start = max(index - radius, 0)
        end = min(index + len(query) + radius, len(content))
        return content[start:end]
