from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ResourceConflictError
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.services.archives import ArchiveService, InMemoryArchiveRepository
from app.services.audit import InMemoryAuditLogWriter


def make_main_project(
    *,
    project_no: str,
    status: MainProjectStatus = MainProjectStatus.closed,
    closed_at: datetime | None,
) -> MainProject:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    return MainProject(
        id=uuid4(),
        project_no=project_no,
        name=f"Main {project_no}",
        dept_id=uuid4(),
        status=status,
        total_budget=Decimal("100000.00"),
        expected_finish_date=now.date(),
        spent_amount=Decimal("10000.00"),
        remark="ready to archive",
        creator_id=uuid4(),
        closed_at=closed_at,
        created_at=now,
        updated_at=now,
    )


def make_sub_project(
    *,
    main_project_id: UUID,
    project_no: str,
    status: SubProjectStatus = SubProjectStatus.closed,
    closed_at: datetime | None,
) -> SubProject:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    return SubProject(
        id=uuid4(),
        project_no=project_no,
        name=f"Sub {project_no}",
        main_project_id=main_project_id,
        dept_id=uuid4(),
        budget=Decimal("20000.00"),
        manager_id=uuid4(),
        creator_id=uuid4(),
        status=status,
        plan_end_date=now.date(),
        actual_end_date=now.date(),
        spent_amount=Decimal("5000.00"),
        remark="child snapshot",
        closed_at=closed_at,
        created_at=now,
        updated_at=now,
    )


def make_admin_user() -> User:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    return User(
        id=uuid4(),
        username="admin",
        email=None,
        password_hash="hashed",
        role=UserRole.admin,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_archive_candidates_require_closed_age_and_no_active_sub_projects() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    eligible = make_main_project(
        project_no="Z-2022-0001",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    recent = make_main_project(
        project_no="Z-2025-0001",
        closed_at=datetime(2025, 5, 10, 9, 0, tzinfo=UTC),
    )
    open_project = make_main_project(
        project_no="Z-2022-0002",
        status=MainProjectStatus.in_progress,
        closed_at=None,
    )
    active_child_project = make_main_project(
        project_no="Z-2022-0003",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    sub_projects = [
        make_sub_project(
            main_project_id=eligible.id,
            project_no="Z-2022-0001-ZX-001",
            status=SubProjectStatus.closed,
            closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
        ),
        make_sub_project(
            main_project_id=active_child_project.id,
            project_no="Z-2022-0003-ZX-001",
            status=SubProjectStatus.in_progress,
            closed_at=None,
        ),
    ]
    repository = InMemoryArchiveRepository(
        projects=[eligible, recent, open_project, active_child_project],
        sub_projects=sub_projects,
    )
    service = ArchiveService(repository=repository, now_provider=lambda: now)

    candidates = await service.list_candidates()

    assert [candidate.main_project_id for candidate in candidates] == [eligible.id]
    assert candidates[0].project_no == "Z-2022-0001"
    assert candidates[0].sub_project_count == 1


@pytest.mark.asyncio
async def test_archive_eligible_projects_writes_archive_rows_and_deletes_sources() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    project = make_main_project(
        project_no="Z-2022-0001",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    keep = make_main_project(
        project_no="Z-2025-0001",
        closed_at=datetime(2025, 5, 10, 9, 0, tzinfo=UTC),
    )
    closed_child = make_sub_project(
        main_project_id=project.id,
        project_no="Z-2022-0001-ZX-001",
        status=SubProjectStatus.closed,
        closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
    )
    terminated_child = make_sub_project(
        main_project_id=project.id,
        project_no="Z-2022-0001-ZX-002",
        status=SubProjectStatus.terminated,
        closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
    )
    repository = InMemoryArchiveRepository(
        projects=[project, keep],
        sub_projects=[closed_child, terminated_child],
    )
    service = ArchiveService(repository=repository, now_provider=lambda: now)

    result = await service.archive_eligible_projects(actor_id=uuid4())

    assert result.batch_no.startswith("ARCH-20260511-")
    assert result.main_projects_before == 2
    assert result.main_projects_after == 1
    assert result.archived_main_project_count == 1
    assert result.archived_sub_project_count == 2
    assert result.duration_ms >= 0
    assert [item.id for item in repository.projects] == [keep.id]
    assert repository.sub_projects == []
    assert len(repository.archive_batches) == 1
    assert repository.archive_main_projects[0].original_id == project.id
    assert repository.archive_main_projects[0].snapshot["status"] == "closed"
    assert repository.archive_sub_projects[1].snapshot["status"] == "terminated"


@pytest.mark.asyncio
async def test_archive_eligible_projects_rolls_back_when_delete_fails() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    project = make_main_project(
        project_no="Z-2022-0001",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    sub_project = make_sub_project(
        main_project_id=project.id,
        project_no="Z-2022-0001-ZX-001",
        status=SubProjectStatus.closed,
        closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
    )
    repository = InMemoryArchiveRepository(
        projects=[project],
        sub_projects=[sub_project],
        fail_on_delete=True,
    )
    service = ArchiveService(repository=repository, now_provider=lambda: now)

    with pytest.raises(RuntimeError, match="delete failed"):
        await service.archive_eligible_projects(actor_id=uuid4())

    assert [item.id for item in repository.projects] == [project.id]
    assert [item.id for item in repository.sub_projects] == [sub_project.id]
    assert repository.archive_batches == []
    assert repository.archive_main_projects == []
    assert repository.archive_sub_projects == []


@pytest.mark.asyncio
async def test_archive_eligible_projects_writes_audit_log() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    actor_id = uuid4()
    project = make_main_project(
        project_no="Z-2022-0001",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    repository = InMemoryArchiveRepository(projects=[project], sub_projects=[])
    service = ArchiveService(repository=repository, now_provider=lambda: now)
    audit_writer = InMemoryAuditLogWriter()

    result = await service.archive_eligible_projects(
        actor_id=actor_id,
        audit_writer=audit_writer,
    )

    assert audit_writer.entries[0].actor_id == actor_id
    assert audit_writer.entries[0].action == "archive.create_batch"
    assert audit_writer.entries[0].target_type == "archive_batch"
    assert audit_writer.entries[0].target_id == str(result.batch_id)
    assert audit_writer.entries[0].after_state["batch_no"] == result.batch_no


@pytest.mark.asyncio
async def test_restore_main_project_restores_sources_removes_archive_rows_and_audits() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    project = make_main_project(
        project_no="Z-2022-0001",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    sub_project = make_sub_project(
        main_project_id=project.id,
        project_no="Z-2022-0001-ZX-001",
        closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
    )
    repository = InMemoryArchiveRepository(projects=[project], sub_projects=[sub_project])
    service = ArchiveService(repository=repository, now_provider=lambda: now)
    await service.archive_eligible_projects(actor_id=uuid4())
    archive_main_project_id = repository.archive_main_projects[0].id
    audit_writer = InMemoryAuditLogWriter()

    restored = await service.restore_main_project(
        actor=make_admin_user(),
        archive_main_project_id=archive_main_project_id,
        audit_writer=audit_writer,
    )

    assert restored.id == project.id
    assert [item.id for item in repository.projects] == [project.id]
    assert [item.id for item in repository.sub_projects] == [sub_project.id]
    assert repository.archive_main_projects == []
    assert repository.archive_sub_projects == []
    assert audit_writer.entries[0].action == "archive.restore_main_project"
    assert audit_writer.entries[0].target_id == str(project.id)
    assert audit_writer.entries[0].extra["restored_sub_project_count"] == 1


@pytest.mark.asyncio
async def test_restore_main_project_rejects_sub_project_no_conflicts() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    project = make_main_project(
        project_no="Z-2022-0001",
        closed_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
    )
    sub_project = make_sub_project(
        main_project_id=project.id,
        project_no="Z-2022-0001-ZX-001",
        closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
    )
    repository = InMemoryArchiveRepository(projects=[project], sub_projects=[sub_project])
    service = ArchiveService(repository=repository, now_provider=lambda: now)
    await service.archive_eligible_projects(actor_id=uuid4())
    archive_main_project_id = repository.archive_main_projects[0].id
    conflicting_sub_project = make_sub_project(
        main_project_id=uuid4(),
        project_no="Z-2022-0001-ZX-001",
        closed_at=datetime(2024, 5, 10, 10, 0, tzinfo=UTC),
    )
    repository.sub_projects.append(conflicting_sub_project)

    with pytest.raises(ResourceConflictError) as exc_info:
        await service.restore_main_project(
            actor=make_admin_user(),
            archive_main_project_id=archive_main_project_id,
        )

    assert exc_info.value.data == {
        "fields": ["sub_project.project_no"],
        "project_nos": ["Z-2022-0001-ZX-001"],
    }
    assert repository.archive_main_projects[0].id == archive_main_project_id
