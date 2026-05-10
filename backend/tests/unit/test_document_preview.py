from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.documents import get_document_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.documents import Document
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.services.audit import AuditContext, InMemoryAuditLogWriter
from app.services.documents import DocumentDownload, DocumentService, InMemoryDocumentRepository
from app.storage.base import StorageBackend
from app.validators.file_validator import FileValidator


class NoopFileValidator(FileValidator):
    def validate(self, *, filename: str, content_type: str | None, content: bytes) -> None:
        return None


class MemoryStorage(StorageBackend):
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        storage_key = f"{sub_id}/{phase_id}/{filename}"
        self.files[storage_key] = content
        return storage_key

    def read(self, storage_key: str) -> bytes:
        return self.files[storage_key]

    def delete(self, storage_key: str) -> None:
        self.files.pop(storage_key, None)

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


class FakeOfficeConverter:
    def __init__(
        self,
        content: bytes = b"%PDF-1.7\nconverted",
        error: BusinessException | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    def convert_to_pdf(self, *, file_name: str, content: bytes) -> bytes:
        self.calls.append((file_name, content))
        if self.error is not None:
            raise self.error
        return self.content


def make_user(role: UserRole, *, username: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_sub_project(manager: User) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no="Z-2026-0001-ZX-001",
        name="采购实施",
        main_project_id=uuid4(),
        dept_id=uuid4(),
        budget=Decimal("100000.00"),
        manager_id=manager.id,
        creator_id=manager.id,
        status=SubProjectStatus.in_progress,
        plan_end_date=date(2026, 10, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark=None,
        created_at=now,
        updated_at=now,
    )


def make_phase(sub_project: SubProject) -> Phase:
    now = datetime.now(UTC)
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=1,
        code="initiation",
        name="立项",
        status=PhaseStatus.in_progress,
        enter_at=now,
        finish_at=None,
        procurement_type=None,
        created_at=now,
        updated_at=now,
    )


def make_document(
    *,
    sub_project: SubProject,
    phase: Phase,
    uploader: User,
    file_name: str,
    doc_type: str = "meeting_material",
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        acceptance_step_id=None,
        doc_type=doc_type,
        file_name=file_name,
        file_path=f"{sub_project.id}/{phase.id}/{file_name}",
        file_size=128,
        version=1,
        is_latest=True,
        is_deleted=False,
        uploader_id=uploader.id,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_preview_pdf_records_audit() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        file_name="meeting.pdf",
    )
    repository = InMemoryDocumentRepository(
        documents=[document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    audit_writer = InMemoryAuditLogWriter()
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage({document.file_path: b"%PDF-1.7\nbody"}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
    )

    preview = await service.preview_document(
        actor=leader,
        document_id=document.id,
        audit_writer=audit_writer,
        audit_context=AuditContext(actor_id=leader.id, request_id="req-preview"),
    )

    assert preview.content == b"%PDF-1.7\nbody"
    assert audit_writer.entries[0].action == "document.preview"
    assert audit_writer.entries[0].target_id == str(document.id)
    assert audit_writer.entries[0].extra["file_name"] == "meeting.pdf"


@pytest.mark.asyncio
async def test_preview_rejects_non_pdf_with_3020() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        file_name="meeting.docx",
    )
    repository = InMemoryDocumentRepository(
        documents=[document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage({document.file_path: b"not-pdf"}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
    )

    with pytest.raises(BusinessException) as exc:
        await service.preview_document(actor=leader, document_id=document.id)

    assert exc.value.code == 3020


@pytest.mark.asyncio
async def test_preview_office_converts_supported_document_and_records_audit() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        file_name="meeting.docx",
    )
    repository = InMemoryDocumentRepository(
        documents=[document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    audit_writer = InMemoryAuditLogWriter()
    converter = FakeOfficeConverter()
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage({document.file_path: b"office-bytes"}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
        office_converter=converter,
    )

    preview = await service.preview_office_document(
        actor=leader,
        document_id=document.id,
        audit_writer=audit_writer,
        audit_context=AuditContext(actor_id=leader.id, request_id="req-office-preview"),
    )

    assert preview.content == b"%PDF-1.7\nconverted"
    assert converter.calls == [("meeting.docx", b"office-bytes")]
    assert audit_writer.entries[0].action == "document.preview_office"
    assert audit_writer.entries[0].target_id == str(document.id)
    assert audit_writer.entries[0].extra["file_name"] == "meeting.docx"


@pytest.mark.asyncio
@pytest.mark.parametrize("file_name", ["meeting.pdf", "diagram.png", "archive.zip"])
async def test_preview_office_rejects_unsupported_documents(file_name: str) -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        file_name=file_name,
    )
    repository = InMemoryDocumentRepository(
        documents=[document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    converter = FakeOfficeConverter()
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage({document.file_path: b"content"}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
        office_converter=converter,
    )

    with pytest.raises(BusinessException) as exc:
        await service.preview_office_document(actor=leader, document_id=document.id)

    assert exc.value.code == 3020
    assert converter.calls == []


@pytest.mark.asyncio
async def test_preview_office_does_not_audit_failed_conversion() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        file_name="meeting.xlsx",
    )
    repository = InMemoryDocumentRepository(
        documents=[document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    audit_writer = InMemoryAuditLogWriter()
    converter = FakeOfficeConverter(
        error=BusinessException(
            code=5003,
            message="Office document conversion failed",
            status_code=503,
        ),
    )
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage({document.file_path: b"broken-office-bytes"}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
        office_converter=converter,
    )

    with pytest.raises(BusinessException) as exc:
        await service.preview_office_document(
            actor=leader,
            document_id=document.id,
            audit_writer=audit_writer,
            audit_context=AuditContext(actor_id=leader.id, request_id="req-office-preview"),
        )

    assert exc.value.code == 5003
    assert audit_writer.entries == []


def test_document_preview_endpoint_streams_inline_pdf() -> None:
    member = make_user(UserRole.proj_member, username="member")
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=member,
        file_name="meeting.pdf",
    )

    class FakeDocumentService:
        async def preview_document(
            self,
            *,
            actor: User,
            document_id: UUID,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> DocumentDownload:
            assert actor.id == member.id
            assert document_id == document.id
            assert audit_writer is not None
            assert audit_context is not None
            return DocumentDownload(document=document, content=b"%PDF-1.7\nbody")

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return member

    async def fake_document_service() -> FakeDocumentService:
        return FakeDocumentService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_document_service] = fake_document_service
    client = TestClient(app)

    response = client.get(f"/api/v1/documents/{document.id}/preview")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7\nbody"
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert "meeting.pdf" in response.headers["content-disposition"]


def test_document_office_preview_endpoint_streams_converted_pdf() -> None:
    member = make_user(UserRole.proj_member, username="member")
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=member,
        file_name="meeting.docx",
    )

    class FakeDocumentService:
        async def preview_office_document(
            self,
            *,
            actor: User,
            document_id: UUID,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> DocumentDownload:
            assert actor.id == member.id
            assert document_id == document.id
            assert audit_writer is not None
            assert audit_context is not None
            return DocumentDownload(document=document, content=b"%PDF-1.7\nconverted")

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return member

    async def fake_document_service() -> FakeDocumentService:
        return FakeDocumentService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_document_service] = fake_document_service
    client = TestClient(app)

    response = client.get(f"/api/v1/documents/{document.id}/preview-office")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7\nconverted"
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert "meeting.pdf" in response.headers["content-disposition"]
