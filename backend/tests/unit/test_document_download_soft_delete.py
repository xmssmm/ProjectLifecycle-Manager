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
from app.services.documents import DocumentDownload, DocumentService, InMemoryDocumentRepository
from app.storage.base import StorageBackend
from app.validators.file_validator import FileValidator


class NoopFileValidator(FileValidator):
    def validate(self, *, filename: str, content_type: str | None, content: bytes) -> None:
        return None


class MemoryStorage(StorageBackend):
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})
        self.deleted: list[str] = []

    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        storage_key = f"{sub_id}/{phase_id}/{len(self.files) + 1}-{filename}"
        self.files[storage_key] = content
        return storage_key

    def read(self, storage_key: str) -> bytes:
        return self.files[storage_key]

    def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)
        self.files.pop(storage_key, None)

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


def make_document(
    *,
    sub_project: SubProject,
    phase: Phase,
    uploader: User,
    version: int,
    is_latest: bool,
    is_deleted: bool = False,
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
        is_deleted=is_deleted,
        uploader_id=uploader.id,
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


@pytest.mark.asyncio
async def test_document_download_allows_v4_member_view_all() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    outsider = make_user(UserRole.proj_member, username="outsider")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        version=1,
        is_latest=True,
    )
    storage = MemoryStorage({document.file_path: b"download-bytes"})
    repository = InMemoryDocumentRepository(
        documents=[document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    service = DocumentService(
        repository=repository,
        storage=storage,
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
    )

    download = await service.download_document(actor=leader, document_id=document.id)

    assert download.document.id == document.id
    assert download.content == b"download-bytes"

    outsider_download = await service.download_document(actor=outsider, document_id=document.id)

    assert outsider_download.document.id == document.id
    assert outsider_download.content == b"download-bytes"


@pytest.mark.asyncio
async def test_soft_delete_phase_documents_hides_latest_but_preserves_history_and_version() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    old_document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        version=1,
        is_latest=False,
    )
    latest_document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        version=2,
        is_latest=True,
    )
    storage = MemoryStorage({latest_document.file_path: b"latest"})
    repository = InMemoryDocumentRepository(
        documents=[old_document, latest_document],
        sub_projects=[sub_project],
        phases=[phase],
    )
    service = DocumentService(
        repository=repository,
        storage=storage,
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
    )

    deleted = await service.soft_delete_phase_documents(phase.id)
    visible = await service.list_documents(actor=leader, sub_project_id=sub_project.id)
    history = await service.list_documents(
        actor=leader,
        sub_project_id=sub_project.id,
        include_history=True,
    )
    new_document = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        file_name="meeting-v3.pdf",
        content_type="application/pdf",
        content=b"new",
    )

    assert deleted == [latest_document]
    assert latest_document.is_deleted is True
    assert latest_document.is_latest is False
    assert visible == []
    assert [document.version for document in history] == [2, 1]
    assert new_document.version == 3
    assert new_document.is_latest is True
    assert storage.deleted == []


def test_document_download_endpoint_streams_file_without_exposing_path() -> None:
    member = make_user(UserRole.proj_member, username="member")
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=member,
        version=1,
        is_latest=True,
    )

    class FakeDocumentService:
        async def download_document(self, *, actor: User, document_id: UUID) -> DocumentDownload:
            assert actor.id == member.id
            assert document_id == document.id
            return DocumentDownload(document=document, content=b"download-bytes")

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

    response = client.get(f"/api/v1/documents/{document.id}/download")

    assert response.status_code == 200
    assert response.content == b"download-bytes"
    assert response.headers["content-type"] == "application/octet-stream"
    assert "meeting-v1.pdf" in response.headers["content-disposition"]
    assert document.file_path not in response.text
