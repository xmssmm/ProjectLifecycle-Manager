from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table, UniqueConstraint

from app.api.v1.documents import get_document_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, ValidationFailedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.documents import Document
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.schemas.documents import DocumentRead
from app.services.documents import DocumentService, InMemoryDocumentRepository
from app.storage.base import StorageBackend, StorageSecurityError


class RecordingStorage(StorageBackend):
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str, bytes]] = []
        self.deleted: list[str] = []

    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        if ".." in filename:
            raise StorageSecurityError("unsafe filename")
        self.saved.append((sub_id, phase_id, filename, content))
        return f"{sub_id}/{phase_id}/{len(self.saved)}-{filename.lower()}"

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


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


def make_member(sub_project: SubProject, user: User) -> SubProjectMember:
    return SubProjectMember(
        id=uuid4(),
        sub_project_id=sub_project.id,
        user_id=user.id,
        role_in_project=SubProjectMemberRole.proj_member,
        joined_at=datetime.now(UTC),
    )


def make_document(
    *,
    sub_project: SubProject,
    phase: Phase,
    uploader: User,
    version: int = 1,
    is_latest: bool = True,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        acceptance_step_id=None,
        doc_type="meeting_material",
        file_name=f"meeting-v{version}.pdf",
        file_path=f"{sub_project.id}/{phase.id}/meeting-v{version}.pdf",
        file_size=128,
        version=version,
        is_latest=is_latest,
        is_deleted=False,
        uploader_id=uploader.id,
        created_at=now,
        updated_at=now,
    )


def test_document_model_has_group_version_unique_constraint_without_latest_unique_index() -> None:
    table = Document.__table__
    assert isinstance(table, Table)

    assert {
        "doc_no",
        "sub_project_id",
        "phase_id",
        "acceptance_step_id",
        "doc_type",
        "file_name",
        "display_name",
        "file_path",
        "file_size",
        "version",
        "is_latest",
        "is_deleted",
        "uploader_id",
    }.issubset(table.columns.keys())
    assert any(
        isinstance(constraint, UniqueConstraint)
        and set(constraint.columns.keys()) == {"sub_project_id", "phase_id", "doc_type", "version"}
        for constraint in table.constraints
    )
    assert not any(index.name == "uq_documents_latest_per_group" for index in table.indexes)


def test_document_read_exposes_display_name_and_uploader_name() -> None:
    uploader = make_user(UserRole.proj_member, username="member")
    sub_project = make_sub_project(uploader)
    phase = make_phase(sub_project)
    document = make_document(sub_project=sub_project, phase=phase, uploader=uploader)
    document.display_name = "Main Contract Scan"
    document.uploader = uploader

    payload = DocumentRead.model_validate(document).model_dump()

    assert payload["display_name"] == "Main Contract Scan"
    assert payload["uploader_name"] == "member"


@pytest.mark.asyncio
async def test_document_service_uploads_versions_and_flips_latest_atomically() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    storage = RecordingStorage()
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    service = DocumentService(
        repository=repository,
        storage=storage,
        max_file_size_bytes=1024,
    )

    first = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        file_name="Meeting.PDF",
        content_type="application/pdf",
        content=b"%PDF-1.7\nfirst",
    )
    second = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        file_name="Meeting-v2.PDF",
        content_type="application/pdf",
        content=b"%PDF-1.7\nsecond",
    )

    assert first.version == 1
    assert first.is_latest is False
    assert second.version == 2
    assert second.is_latest is True
    assert second.file_path == f"{sub_project.id}/{phase.id}/2-meeting-v2.pdf"
    assert storage.saved == [
        (str(sub_project.id), str(phase.id), "Meeting.PDF", b"%PDF-1.7\nfirst"),
        (str(sub_project.id), str(phase.id), "Meeting-v2.PDF", b"%PDF-1.7\nsecond"),
    ]

    latest = await service.list_documents(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        include_history=False,
    )
    history = await service.list_documents(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        include_history=True,
    )

    assert [document.version for document in latest] == [2]
    assert [document.version for document in history] == [2, 1]


@pytest.mark.asyncio
async def test_upload_document_persists_display_name() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    storage = RecordingStorage()
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    service = DocumentService(
        repository=repository,
        storage=storage,
        max_file_size_bytes=1024,
    )

    document = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="contract",
        file_name="uuid-contract.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7\ncontract",
        display_name="Main Contract Scan",
    )

    assert document.display_name == "Main Contract Scan"


@pytest.mark.asyncio
async def test_upload_multi_instance_documents_keeps_each_file_latest() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    service = DocumentService(
        repository=repository,
        storage=RecordingStorage(),
        max_file_size_bytes=1024,
    )

    first = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="supplier_quote",
        file_name="quote-1.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7\nquote-1",
    )
    second = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="supplier_quote",
        file_name="quote-2.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7\nquote-2",
    )

    assert first.version == 1
    assert second.version == 2
    assert first.is_latest is True
    assert second.is_latest is True
    latest = await service.list_documents(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="supplier_quote",
    )
    assert {document.id for document in latest} == {first.id, second.id}


@pytest.mark.asyncio
async def test_delete_document_soft_deletes_and_restores_previous_version() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    first = make_document(sub_project=sub_project, phase=phase, uploader=leader, is_latest=False)
    second = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        version=2,
        is_latest=True,
    )
    repository = InMemoryDocumentRepository(
        documents=[first, second],
        phases=[phase],
        sub_projects=[sub_project],
    )
    service = DocumentService(
        repository=repository,
        storage=RecordingStorage(),
        max_file_size_bytes=1024,
    )

    deleted = await service.delete_document(actor=leader, document_id=second.id)

    assert deleted.is_deleted is True
    assert deleted.is_latest is False
    assert first.is_latest is True


@pytest.mark.asyncio
async def test_upload_document_rejects_completed_sub_project_and_completed_phase() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    sub_project.status = SubProjectStatus.completed
    phase = make_phase(sub_project)
    service = DocumentService(
        repository=InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase]),
        storage=RecordingStorage(),
        max_file_size_bytes=1024,
    )

    with pytest.raises(BusinessException) as completed_sub_project:
        await service.upload_document(
            actor=leader,
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type="meeting_material",
            file_name="meeting.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.7\nbody",
        )

    assert completed_sub_project.value.message == "已完成或已结项子项目禁止上传文件"

    sub_project.status = SubProjectStatus.in_progress
    phase.status = PhaseStatus.completed
    with pytest.raises(BusinessException) as completed_phase:
        await service.upload_document(
            actor=leader,
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type="meeting_material",
            file_name="meeting.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.7\nbody",
        )

    assert completed_phase.value.message == "已完成环节禁止上传文件"


@pytest.mark.asyncio
async def test_document_service_allows_project_member_view_all_and_rejects_invalid_files() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    project_member = make_user(UserRole.proj_member, username="project-member")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    storage = RecordingStorage()
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    service = DocumentService(
        repository=repository,
        storage=storage,
        max_file_size_bytes=4,
    )

    uploaded = await service.upload_document(
        actor=project_member,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        file_name="meeting.pdf",
        content_type="application/pdf",
        content=b"%PDF",
    )

    assert uploaded.uploader_id == project_member.id

    with pytest.raises(ValidationFailedError):
        await service.upload_document(
            actor=leader,
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type="meeting_material",
            file_name="meeting.pdf",
            content_type="application/pdf",
            content=b"large",
        )

    with pytest.raises(ValidationFailedError):
        await service.upload_document(
            actor=leader,
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type="meeting_material",
            file_name="../evil.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.7\nok",
        )

    assert repository.documents == [uploaded]
    assert len(storage.saved) == 1


@pytest.mark.asyncio
async def test_document_service_rejects_content_above_50mb_limit_without_writing_storage() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    storage = RecordingStorage()
    service = DocumentService(
        repository=InMemoryDocumentRepository(),
        storage=storage,
        max_file_size_bytes=50 * 1024 * 1024,
    )

    with pytest.raises(ValidationFailedError):
        await service.upload_document(
            actor=leader,
            sub_project_id=uuid4(),
            phase_id=uuid4(),
            doc_type="meeting_material",
            file_name="meeting.pdf",
            content_type="application/pdf",
            content=b"x" * (50 * 1024 * 1024 + 1),
        )

    assert storage.saved == []


def test_document_upload_and_list_endpoints_return_doc_id_and_version() -> None:
    member = make_user(UserRole.proj_member, username="member")
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(sub_project=sub_project, phase=phase, uploader=member)

    class FakeDocumentService:
        async def upload_document(
            self,
            *,
            actor: User,
            sub_project_id: UUID,
            phase_id: UUID,
            doc_type: str,
            file_name: str,
            display_name: str | None = None,
            content_type: str | None,
            content: bytes,
            acceptance_step_id: UUID | None = None,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> Document:
            assert actor.id == member.id
            assert sub_project_id == sub_project.id
            assert phase_id == phase.id
            assert doc_type == document.doc_type
            assert file_name == "meeting.pdf"
            assert display_name is None
            assert content_type == "application/pdf"
            assert content == b"file-bytes"
            assert acceptance_step_id is None
            assert audit_writer is not None
            assert audit_context is not None
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
            assert actor.id == member.id
            assert sub_project_id == sub_project.id
            assert phase_id == phase.id
            assert doc_type == document.doc_type
            assert include_history is True
            return [document]

        async def delete_document(self, *, actor: User, document_id: UUID) -> Document:
            assert actor.id == member.id
            assert document_id == document.id
            document.is_deleted = True
            return document

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

    upload_response = client.post(
        "/api/v1/documents",
        data={
            "sub_project_id": str(sub_project.id),
            "phase_id": str(phase.id),
            "doc_type": document.doc_type,
        },
        files={"file": ("meeting.pdf", b"file-bytes", "application/pdf")},
    )
    list_response = client.get(
        "/api/v1/documents",
        params={
            "sub_project_id": str(sub_project.id),
            "phase_id": str(phase.id),
            "doc_type": document.doc_type,
            "include_history": "true",
        },
    )
    delete_response = client.delete(f"/api/v1/documents/{document.id}")

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()["data"]
    assert upload_payload["doc_id"] == str(document.id)
    assert upload_payload["version"] == 1
    assert "file_path" not in upload_payload

    assert list_response.status_code == 200
    list_payload = list_response.json()["data"]
    assert list_payload["items"][0]["id"] == str(document.id)
    assert list_payload["items"][0]["version"] == 1
    assert "file_path" not in list_payload["items"][0]
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["is_deleted"] is True
