from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.services.audit import AuditContext, InMemoryAuditLogWriter
from app.services.documents import DocumentService, InMemoryDocumentRepository
from app.storage.base import StorageBackend
from app.validators.file_validator import (
    BLOCKED_EXTENSIONS,
    DefaultFileValidator,
    FileValidationError,
)


class RecordingStorage(StorageBackend):
    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        return f"{sub_id}/{phase_id}/{filename}"

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        return None

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


def make_zip(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


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


def test_file_validator_allows_valid_pdf() -> None:
    validator = DefaultFileValidator()

    validator.validate(
        filename="meeting.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7\nbody",
    )


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "reason"),
    [
        ("notes.txt", "text/plain", b"hello", "extension_not_allowed"),
        ("meeting.pdf", "application/x-msdownload", b"%PDF-1.7\nbody", "mime_not_allowed"),
        ("meeting.pdf", "application/pdf", b"MZ\x90\x00payload", "magic_mismatch"),
    ],
)
def test_file_validator_rejects_extension_mime_and_magic_failures(
    filename: str,
    content_type: str,
    content: bytes,
    reason: str,
) -> None:
    validator = DefaultFileValidator()

    with pytest.raises(FileValidationError) as exc:
        validator.validate(filename=filename, content_type=content_type, content=content)

    assert exc.value.reason == reason
    assert exc.value.data == {"rejection_reason": reason}


def test_file_validator_rejects_zip_containing_blocked_extension() -> None:
    validator = DefaultFileValidator()
    content = make_zip({"safe/readme.txt": b"ok", "bin/setup.exe": b"MZ"})

    with pytest.raises(FileValidationError) as exc:
        validator.validate(filename="bundle.zip", content_type="application/zip", content=content)

    assert exc.value.reason == "zip_contains_blocked_extension"


def test_file_validator_blacklist_matches_requirements_br_doc_04() -> None:
    assert BLOCKED_EXTENSIONS == {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".pif",
        ".ps1",
        ".psm1",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".wsf",
        ".wsh",
        ".msi",
        ".msp",
        ".dll",
        ".sh",
        ".bash",
        ".zsh",
        ".jar",
        ".app",
    }


@pytest.mark.asyncio
async def test_document_upload_rejection_records_audit_reason() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    repository = InMemoryDocumentRepository(sub_projects=[sub_project], phases=[phase])
    audit_writer = InMemoryAuditLogWriter()
    service = DocumentService(
        repository=repository,
        storage=RecordingStorage(),
        max_file_size_bytes=1024,
        file_validator=DefaultFileValidator(),
    )

    with pytest.raises(ValidationFailedError):
        await service.upload_document(
            actor=leader,
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type="meeting_material",
            file_name="meeting.pdf",
            content_type="application/pdf",
            content=b"MZ\x90\x00payload",
            audit_writer=audit_writer,
            audit_context=AuditContext(actor_id=leader.id, request_id="req-upload-rejected"),
        )

    assert repository.documents == []
    assert audit_writer.entries[0].action == "upload_rejected"
    assert audit_writer.entries[0].target_type == "document"
    assert audit_writer.entries[0].target_id == str(phase.id)
    assert audit_writer.entries[0].extra["rejection_reason"] == "magic_mismatch"
