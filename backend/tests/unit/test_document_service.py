from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import BusinessException
from app.models.documents import Document, DocumentScanStatus
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.services.documents import DocumentService, InMemoryDocumentRepository
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.virus_scan import (
    EICAR_TEST_CONTENT,
    DocumentScanService,
    EicarSignatureVirusScanner,
    InMemoryDocumentScanRepository,
)
from app.storage.base import StorageBackend
from app.validators.file_validator import FileValidator


class NoopFileValidator(FileValidator):
    def validate(self, *, filename: str, content_type: str | None, content: bytes) -> None:
        return None


class MemoryStorage(StorageBackend):
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})

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
        self.files.pop(storage_key, None)

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


class RecordingScanScheduler:
    def __init__(self) -> None:
        self.document_ids: list[UUID] = []

    def enqueue(self, document_id: UUID) -> None:
        self.document_ids.append(document_id)


class RecordingSearchScheduler:
    def __init__(self) -> None:
        self.document_ids: list[UUID] = []

    def enqueue(self, document_id: UUID) -> None:
        self.document_ids.append(document_id)


class FailingScanScheduler:
    def enqueue(self, document_id: UUID) -> None:
        _ = document_id
        raise RuntimeError("broker unavailable")


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
    scan_status: DocumentScanStatus,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        acceptance_step_id=None,
        doc_type="meeting_material",
        file_name="meeting.pdf",
        file_path=f"{sub_project.id}/{phase.id}/meeting.pdf",
        file_size=128,
        version=1,
        is_latest=True,
        is_deleted=False,
        uploader_id=uploader.id,
        scan_status=scan_status,
        scan_result=None,
        scanned_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_upload_sets_document_pending_and_enqueues_scan() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    scheduler = RecordingScanScheduler()
    search_scheduler = RecordingSearchScheduler()
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage(),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
        scan_scheduler=scheduler,
        search_scheduler=search_scheduler,
    )

    document = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        file_name="meeting.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7\nbody",
    )

    assert document.scan_status == DocumentScanStatus.pending
    assert document.scan_result is None
    assert document.scanned_at is None
    assert scheduler.document_ids == [document.id]
    assert search_scheduler.document_ids == [document.id]


@pytest.mark.asyncio
async def test_upload_marks_scan_failed_when_enqueue_fails() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    service = DocumentService(
        repository=repository,
        storage=MemoryStorage(),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
        scan_scheduler=FailingScanScheduler(),
    )

    document = await service.upload_document(
        actor=leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="meeting_material",
        file_name="meeting.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7\nbody",
    )

    assert document.scan_status == DocumentScanStatus.failed
    assert document.scan_result == "Scan scheduling failed: broker unavailable"
    assert document.scanned_at is not None
    with pytest.raises(BusinessException) as exc:
        await service.download_document(actor=leader, document_id=document.id)
    assert exc.value.code == 3032


@pytest.mark.asyncio
async def test_pending_document_is_visible_and_downloadable_without_scan_status_blocker() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        scan_status=DocumentScanStatus.pending,
    )
    service = DocumentService(
        repository=InMemoryDocumentRepository(
            documents=[document],
            sub_projects=[sub_project],
            phases=[phase],
        ),
        storage=MemoryStorage({document.file_path: b"%PDF-1.7\nbody"}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
    )

    visible = await service.list_documents(actor=leader, sub_project_id=sub_project.id)
    download = await service.download_document(actor=leader, document_id=document.id)
    preview = await service.preview_document(actor=leader, document_id=document.id)

    assert visible == [document]
    assert download.content == b"%PDF-1.7\nbody"
    assert preview.content == b"%PDF-1.7\nbody"


@pytest.mark.asyncio
async def test_infected_document_download_is_blocked() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=leader,
        scan_status=DocumentScanStatus.infected,
    )
    service = DocumentService(
        repository=InMemoryDocumentRepository(
            documents=[document],
            sub_projects=[sub_project],
            phases=[phase],
        ),
        storage=MemoryStorage({document.file_path: EICAR_TEST_CONTENT}),
        max_file_size_bytes=1024,
        file_validator=NoopFileValidator(),
    )

    with pytest.raises(BusinessException) as exc:
        await service.download_document(actor=leader, document_id=document.id)
    with pytest.raises(BusinessException) as preview_exc:
        await service.preview_document(actor=leader, document_id=document.id)

    assert exc.value.code == 3031
    assert preview_exc.value.code == 3031


@pytest.mark.asyncio
async def test_scan_service_marks_infected_and_notifies_uploader_and_admin() -> None:
    uploader = make_user(UserRole.proj_leader, username="uploader")
    admin = make_user(UserRole.admin, username="admin")
    sub_project = make_sub_project(uploader)
    phase = make_phase(sub_project)
    document = make_document(
        sub_project=sub_project,
        phase=phase,
        uploader=uploader,
        scan_status=DocumentScanStatus.pending,
    )
    scan_repository = InMemoryDocumentScanRepository(
        documents=[document],
        admin_user_ids=[admin.id],
    )
    notification_repository = InMemoryNotificationRepository()
    service = DocumentScanService(
        repository=scan_repository,
        storage=MemoryStorage({document.file_path: EICAR_TEST_CONTENT}),
        scanner=EicarSignatureVirusScanner(),
        notification_service=NotificationService(repository=notification_repository),
    )

    result = await service.scan_document(document.id)

    assert result.status == DocumentScanStatus.infected
    assert document.scan_status == DocumentScanStatus.infected
    assert "EICAR-Test-File" in str(document.scan_result)
    assert document.scanned_at is not None
    assert {item.receiver_id for item in notification_repository.notifications} == {
        uploader.id,
        admin.id,
    }
    assert {item.scenario for item in notification_repository.notifications} == {
        "document_infected",
    }
