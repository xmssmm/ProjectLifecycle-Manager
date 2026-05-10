from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError, ValidationFailedError
from app.models.documents import Document
from app.models.phases import Phase
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.users import User, UserRole
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter
from app.storage.base import StorageBackend, StorageSecurityError
from app.validators.file_validator import DefaultFileValidator, FileValidationError, FileValidator

VIEW_ALL_DOCUMENT_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)


@dataclass(frozen=True)
class DocumentDownload:
    document: Document
    content: bytes


class DocumentRepository(Protocol):
    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def get_document(self, document_id: UUID) -> Document | None:
        ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def list_group_documents_for_update(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
    ) -> list[Document]:
        ...

    async def list_documents(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID | None = None,
        doc_type: str | None = None,
        include_history: bool = False,
    ) -> list[Document]:
        ...

    async def list_latest_phase_documents_for_update(self, phase_id: UUID) -> list[Document]:
        ...

    def add(self, document: Document) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, document: Document) -> None:
        ...


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.get(SubProject, sub_project_id)
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        phase = await self._session.get(Phase, phase_id)
        return phase if isinstance(phase, Phase) else None

    async def get_document(self, document_id: UUID) -> Document | None:
        document = await self._session.get(Document, document_id)
        return document if isinstance(document, Document) else None

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        member = await self._session.scalar(
            select(SubProjectMember).where(
                SubProjectMember.sub_project_id == sub_project_id,
                SubProjectMember.user_id == user_id,
            ),
        )
        return member if isinstance(member, SubProjectMember) else None

    async def list_group_documents_for_update(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
    ) -> list[Document]:
        result = await self._session.scalars(
            select(Document)
            .where(
                Document.sub_project_id == sub_project_id,
                Document.phase_id == phase_id,
                Document.doc_type == doc_type,
            )
            .order_by(Document.version.desc())
            .with_for_update(),
        )
        return list(result.all())

    async def list_documents(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID | None = None,
        doc_type: str | None = None,
        include_history: bool = False,
    ) -> list[Document]:
        conditions = [Document.sub_project_id == sub_project_id]
        if phase_id is not None:
            conditions.append(Document.phase_id == phase_id)
        if doc_type is not None:
            conditions.append(Document.doc_type == doc_type)
        if not include_history:
            conditions.extend([Document.is_latest.is_(True), Document.is_deleted.is_(False)])

        result = await self._session.scalars(
            select(Document)
            .where(*conditions)
            .order_by(Document.doc_type.asc(), Document.version.desc(), Document.created_at.desc()),
        )
        return list(result.all())

    async def list_latest_phase_documents_for_update(self, phase_id: UUID) -> list[Document]:
        result = await self._session.scalars(
            select(Document)
            .where(
                Document.phase_id == phase_id,
                Document.is_latest.is_(True),
            )
            .order_by(Document.doc_type.asc(), Document.version.desc())
            .with_for_update(),
        )
        return list(result.all())

    def add(self, document: Document) -> None:
        self._session.add(document)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, document: Document) -> None:
        await self._session.refresh(document)


class InMemoryDocumentRepository:
    def __init__(
        self,
        *,
        documents: list[Document] | None = None,
        phases: list[Phase] | None = None,
        sub_projects: list[SubProject] | None = None,
        members: list[SubProjectMember] | None = None,
    ) -> None:
        self.documents = list(documents or [])
        self.phases = list(phases or [])
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        return next((phase for phase in self.phases if phase.id == phase_id), None)

    async def get_document(self, document_id: UUID) -> Document | None:
        return next((document for document in self.documents if document.id == document_id), None)

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        return next(
            (
                member
                for member in self.members
                if member.sub_project_id == sub_project_id and member.user_id == user_id
            ),
            None,
        )

    async def list_group_documents_for_update(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
    ) -> list[Document]:
        documents = [
            document
            for document in self.documents
            if document.sub_project_id == sub_project_id
            and document.phase_id == phase_id
            and document.doc_type == doc_type
        ]
        return sorted(documents, key=lambda document: document.version, reverse=True)

    async def list_documents(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID | None = None,
        doc_type: str | None = None,
        include_history: bool = False,
    ) -> list[Document]:
        documents = [
            document for document in self.documents if document.sub_project_id == sub_project_id
        ]
        if phase_id is not None:
            documents = [document for document in documents if document.phase_id == phase_id]
        if doc_type is not None:
            documents = [document for document in documents if document.doc_type == doc_type]
        if not include_history:
            documents = [
                document
                for document in documents
                if document.is_latest and not document.is_deleted
            ]
        return sorted(documents, key=lambda document: (document.doc_type, -document.version))

    async def list_latest_phase_documents_for_update(self, phase_id: UUID) -> list[Document]:
        documents = [
            document
            for document in self.documents
            if document.phase_id == phase_id and document.is_latest
        ]
        return sorted(documents, key=lambda document: (document.doc_type, -document.version))

    def add(self, document: Document) -> None:
        self.documents.append(document)

    async def commit(self) -> None:
        return None

    async def refresh(self, document: Document) -> None:
        return None


class DocumentService:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: StorageBackend,
        max_file_size_bytes: int,
        file_validator: FileValidator | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_file_size_bytes = max_file_size_bytes
        self._file_validator = file_validator or DefaultFileValidator()

    async def upload_document(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
        file_name: str,
        content_type: str | None = None,
        content: bytes,
        acceptance_step_id: UUID | None = None,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> Document:
        cleaned_doc_type = self._clean_doc_type(doc_type)
        cleaned_file_name = self._clean_file_name(file_name)
        self._ensure_file_size_allowed(content)
        sub_project, phase = await self._get_existing_scope(
            sub_project_id=sub_project_id,
            phase_id=phase_id,
        )
        await self._ensure_visible(actor, sub_project)
        self._validate_file(
            actor=actor,
            phase=phase,
            doc_type=cleaned_doc_type,
            file_name=cleaned_file_name,
            content_type=content_type,
            content=content,
            audit_writer=audit_writer,
            audit_context=audit_context,
        )
        group_documents = await self._repository.list_group_documents_for_update(
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type=cleaned_doc_type,
        )
        next_version = max((document.version for document in group_documents), default=0) + 1
        for document in group_documents:
            if document.is_latest:
                document.is_latest = False

        storage_key = self._save_content(
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            file_name=cleaned_file_name,
            content=content,
        )
        now = datetime.now(UTC)
        document = Document(
            id=uuid4(),
            doc_no=str(uuid4()),
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            acceptance_step_id=acceptance_step_id,
            doc_type=cleaned_doc_type,
            file_name=cleaned_file_name,
            file_path=storage_key,
            file_size=len(content),
            version=next_version,
            is_latest=True,
            is_deleted=False,
            uploader_id=actor.id,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(document)
        try:
            await self._repository.commit()
        except Exception:
            self._delete_saved_content(storage_key)
            raise
        await self._repository.refresh(document)
        return document

    async def list_documents(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        phase_id: UUID | None = None,
        doc_type: str | None = None,
        include_history: bool = False,
    ) -> list[Document]:
        sub_project = await self._repository.get_sub_project(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        await self._ensure_visible(actor, sub_project)
        cleaned_doc_type = self._clean_optional_doc_type(doc_type)
        if phase_id is not None:
            phase = await self._repository.get_phase(phase_id)
            if phase is None or phase.sub_project_id != sub_project_id:
                raise ResourceNotFoundError("Phase does not exist")
        return await self._repository.list_documents(
            sub_project_id=sub_project_id,
            phase_id=phase_id,
            doc_type=cleaned_doc_type,
            include_history=include_history,
        )

    async def download_document(self, *, actor: User, document_id: UUID) -> DocumentDownload:
        document = await self._repository.get_document(document_id)
        if document is None:
            raise ResourceNotFoundError("Document does not exist")
        sub_project = await self._repository.get_sub_project(document.sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        await self._ensure_visible(actor, sub_project)
        return DocumentDownload(
            document=document,
            content=self._storage.read(document.file_path),
        )

    async def soft_delete_phase_documents(self, phase_id: UUID) -> list[Document]:
        phase = await self._repository.get_phase(phase_id)
        if phase is None:
            raise ResourceNotFoundError("Phase does not exist")
        documents = await self._repository.list_latest_phase_documents_for_update(phase_id)
        now = datetime.now(UTC)
        for document in documents:
            document.is_deleted = True
            document.updated_at = now
        await self._repository.commit()
        for document in documents:
            await self._repository.refresh(document)
        return documents

    async def _get_existing_scope(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
    ) -> tuple[SubProject, Phase]:
        sub_project = await self._repository.get_sub_project(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        phase = await self._repository.get_phase(phase_id)
        if phase is None or phase.sub_project_id != sub_project_id:
            raise ResourceNotFoundError("Phase does not exist")
        return sub_project, phase

    async def _ensure_visible(self, actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_DOCUMENT_ROLES or sub_project.manager_id == actor.id:
            return
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=actor.id,
        )
        if member is not None:
            return
        raise PermissionDeniedError()

    def _ensure_file_size_allowed(self, content: bytes) -> None:
        if len(content) > self._max_file_size_bytes:
            raise ValidationFailedError("File exceeds maximum upload size")

    @staticmethod
    def _clean_doc_type(doc_type: str) -> str:
        cleaned = doc_type.strip()
        if not cleaned:
            raise ValidationFailedError("Document type is required")
        return cleaned

    @classmethod
    def _clean_optional_doc_type(cls, doc_type: str | None) -> str | None:
        if doc_type is None:
            return None
        return cls._clean_doc_type(doc_type)

    @staticmethod
    def _clean_file_name(file_name: str) -> str:
        cleaned = file_name.strip()
        if not cleaned:
            raise ValidationFailedError("File name is required")
        return cleaned

    def _save_content(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        file_name: str,
        content: bytes,
    ) -> str:
        try:
            return self._storage.save(
                sub_id=str(sub_project_id),
                phase_id=str(phase_id),
                filename=file_name,
                content=content,
            )
        except StorageSecurityError as exc:
            raise ValidationFailedError("File name contains unsafe path characters") from exc

    def _validate_file(
        self,
        *,
        actor: User,
        phase: Phase,
        doc_type: str,
        file_name: str,
        content_type: str | None,
        content: bytes,
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
    ) -> None:
        try:
            self._file_validator.validate(
                filename=file_name,
                content_type=content_type,
                content=content,
            )
        except FileValidationError as exc:
            self._record_upload_rejected(
                actor=actor,
                phase=phase,
                doc_type=doc_type,
                file_name=file_name,
                content_type=content_type,
                reason=exc.reason,
                audit_writer=audit_writer,
                audit_context=audit_context,
            )
            raise

    @staticmethod
    def _record_upload_rejected(
        *,
        actor: User,
        phase: Phase,
        doc_type: str,
        file_name: str,
        content_type: str | None,
        reason: str,
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id,
                action="upload_rejected",
                target_type="document",
                target_id=str(phase.id),
                before_state={},
                after_state={},
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={
                    "rejection_reason": reason,
                    "doc_type": doc_type,
                    "file_name": file_name,
                    "content_type": content_type or "",
                },
                request_id=context.request_id,
            ),
        )

    def _delete_saved_content(self, storage_key: str) -> None:
        try:
            self._storage.delete(storage_key)
        except Exception:
            return
