from __future__ import annotations

import enum
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceConflictError, ResourceNotFoundError
from app.models.acceptance_steps import AcceptanceStep
from app.models.archives import ArchiveBatch, ArchiveMainProject, ArchiveSubProject
from app.models.documents import Document
from app.models.handover_requests import HandoverRequestProject
from app.models.main_projects import MainProject, MainProjectStatus, ProjectReview
from app.models.payments import Payment, PaymentType, PaymentVoucher
from app.models.phases import Phase, PhaseHistory
from app.models.revoke_requests import RevokeRequest
from app.models.sub_projects import (
    SubProject,
    SubProjectHandover,
    SubProjectMember,
    SubProjectNoCounter,
    SubProjectStatus,
)
from app.models.tasks import Task, TaskExecutor
from app.models.users import User, UserRole
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter, to_audit_state

ARCHIVE_RETENTION_DAYS = 365 * 2
ARCHIVABLE_SUB_PROJECT_STATUSES = {SubProjectStatus.closed, SubProjectStatus.terminated}


@dataclass(frozen=True)
class ArchiveCandidate:
    main_project_id: UUID
    project_no: str
    name: str
    closed_at: datetime
    sub_project_count: int


@dataclass(frozen=True)
class ArchiveRunResult:
    batch_id: UUID
    batch_no: str
    archived_main_project_count: int
    archived_sub_project_count: int
    main_projects_before: int
    main_projects_after: int
    duration_ms: int


@dataclass(frozen=True)
class ArchiveBatchPage:
    items: list[ArchiveBatch]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class ArchiveBatchDetail:
    batch: ArchiveBatch
    main_projects: list[ArchiveMainProject]
    sub_projects: list[ArchiveSubProject]


class ArchiveRepository(Protocol):
    def begin(self) -> None:
        ...

    async def list_candidate_projects(self, cutoff_at: datetime) -> list[MainProject]:
        ...

    async def list_sub_projects_by_main_project_ids(
        self,
        main_project_ids: Sequence[UUID],
    ) -> list[SubProject]:
        ...

    async def count_main_projects(self) -> int:
        ...

    async def list_batches(self, *, page: int, page_size: int) -> tuple[list[ArchiveBatch], int]:
        ...

    async def get_batch(self, batch_id: UUID) -> ArchiveBatch | None:
        ...

    async def list_archive_main_projects(self, batch_id: UUID) -> list[ArchiveMainProject]:
        ...

    async def list_archive_sub_projects(self, batch_id: UUID) -> list[ArchiveSubProject]:
        ...

    async def get_archive_main_project(
        self,
        archive_main_project_id: UUID,
    ) -> ArchiveMainProject | None:
        ...

    async def list_archive_sub_projects_for_main(
        self,
        *,
        batch_id: UUID,
        original_main_project_id: UUID,
    ) -> list[ArchiveSubProject]:
        ...

    async def main_project_no_exists(self, project_no: str) -> bool:
        ...

    async def sub_project_no_conflicts(self, project_nos: Sequence[str]) -> list[str]:
        ...

    def restore_main_project(
        self,
        project: MainProject,
        sub_projects: Sequence[SubProject],
    ) -> None:
        ...

    async def delete_archive_project_snapshots(
        self,
        *,
        archive_main_project_id: UUID,
        archive_sub_project_ids: Sequence[UUID],
    ) -> None:
        ...

    def add_batch(self, batch: ArchiveBatch) -> None:
        ...

    def add_archive_main_project(self, archive: ArchiveMainProject) -> None:
        ...

    def add_archive_sub_project(self, archive: ArchiveSubProject) -> None:
        ...

    async def delete_project_graph(self, main_project_ids: Sequence[UUID]) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class SqlAlchemyArchiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def begin(self) -> None:
        return None

    async def list_candidate_projects(self, cutoff_at: datetime) -> list[MainProject]:
        active_child_exists = (
            select(SubProject.id)
            .where(
                SubProject.main_project_id == MainProject.id,
                SubProject.status.notin_(list(ARCHIVABLE_SUB_PROJECT_STATUSES)),
            )
            .exists()
        )
        result = await self._session.scalars(
            select(MainProject)
            .where(
                MainProject.status == MainProjectStatus.closed,
                MainProject.closed_at.is_not(None),
                MainProject.closed_at <= cutoff_at,
                ~active_child_exists,
            )
            .order_by(MainProject.closed_at.asc(), MainProject.project_no.asc()),
        )
        return list(result.all())

    async def list_sub_projects_by_main_project_ids(
        self,
        main_project_ids: Sequence[UUID],
    ) -> list[SubProject]:
        if not main_project_ids:
            return []
        result = await self._session.scalars(
            select(SubProject)
            .where(SubProject.main_project_id.in_(main_project_ids))
            .order_by(SubProject.project_no.asc()),
        )
        return list(result.all())

    async def count_main_projects(self) -> int:
        total = await self._session.scalar(select(func.count()).select_from(MainProject))
        return int(total or 0)

    async def list_batches(self, *, page: int, page_size: int) -> tuple[list[ArchiveBatch], int]:
        total = await self._session.scalar(select(func.count()).select_from(ArchiveBatch))
        result = await self._session.scalars(
            select(ArchiveBatch)
            .order_by(ArchiveBatch.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
        return list(result.all()), int(total or 0)

    async def get_batch(self, batch_id: UUID) -> ArchiveBatch | None:
        batch = await self._session.get(ArchiveBatch, batch_id)
        return batch if isinstance(batch, ArchiveBatch) else None

    async def list_archive_main_projects(self, batch_id: UUID) -> list[ArchiveMainProject]:
        result = await self._session.scalars(
            select(ArchiveMainProject)
            .where(ArchiveMainProject.batch_id == batch_id)
            .order_by(ArchiveMainProject.project_no.asc()),
        )
        return list(result.all())

    async def list_archive_sub_projects(self, batch_id: UUID) -> list[ArchiveSubProject]:
        result = await self._session.scalars(
            select(ArchiveSubProject)
            .where(ArchiveSubProject.batch_id == batch_id)
            .order_by(ArchiveSubProject.project_no.asc()),
        )
        return list(result.all())

    async def get_archive_main_project(
        self,
        archive_main_project_id: UUID,
    ) -> ArchiveMainProject | None:
        archive = await self._session.get(ArchiveMainProject, archive_main_project_id)
        return archive if isinstance(archive, ArchiveMainProject) else None

    async def list_archive_sub_projects_for_main(
        self,
        *,
        batch_id: UUID,
        original_main_project_id: UUID,
    ) -> list[ArchiveSubProject]:
        result = await self._session.scalars(
            select(ArchiveSubProject)
            .where(
                ArchiveSubProject.batch_id == batch_id,
                ArchiveSubProject.original_main_project_id == original_main_project_id,
            )
            .order_by(ArchiveSubProject.project_no.asc()),
        )
        return list(result.all())

    async def main_project_no_exists(self, project_no: str) -> bool:
        total = await self._session.scalar(
            select(func.count())
            .select_from(MainProject)
            .where(MainProject.project_no == project_no),
        )
        return bool(total)

    async def sub_project_no_conflicts(self, project_nos: Sequence[str]) -> list[str]:
        if not project_nos:
            return []
        result = await self._session.scalars(
            select(SubProject.project_no).where(SubProject.project_no.in_(project_nos)),
        )
        return list(result.all())

    def restore_main_project(
        self,
        project: MainProject,
        sub_projects: Sequence[SubProject],
    ) -> None:
        self._session.add(project)
        self._session.add_all(list(sub_projects))

    async def delete_archive_project_snapshots(
        self,
        *,
        archive_main_project_id: UUID,
        archive_sub_project_ids: Sequence[UUID],
    ) -> None:
        if archive_sub_project_ids:
            await self._session.execute(
                delete(ArchiveSubProject).where(
                    ArchiveSubProject.id.in_(archive_sub_project_ids),
                ),
            )
        await self._session.execute(
            delete(ArchiveMainProject).where(ArchiveMainProject.id == archive_main_project_id),
        )

    def add_batch(self, batch: ArchiveBatch) -> None:
        self._session.add(batch)

    def add_archive_main_project(self, archive: ArchiveMainProject) -> None:
        self._session.add(archive)

    def add_archive_sub_project(self, archive: ArchiveSubProject) -> None:
        self._session.add(archive)

    async def delete_project_graph(self, main_project_ids: Sequence[UUID]) -> None:
        if not main_project_ids:
            return

        sub_project_ids = await self._ids(
            select(SubProject.id).where(SubProject.main_project_id.in_(main_project_ids)),
        )
        phase_ids = await self._ids(
            select(Phase.id).where(Phase.sub_project_id.in_(sub_project_ids)),
        )
        task_ids = await self._ids(
            select(Task.id).where(Task.sub_project_id.in_(sub_project_ids)),
        )
        payment_ids = await self._ids(
            select(Payment.id).where(Payment.sub_project_id.in_(sub_project_ids)),
        )
        document_ids = await self._ids(
            select(Document.id).where(Document.sub_project_id.in_(sub_project_ids)),
        )

        if payment_ids or document_ids:
            voucher_conditions = []
            if payment_ids:
                voucher_conditions.append(PaymentVoucher.payment_id.in_(payment_ids))
            if document_ids:
                voucher_conditions.append(PaymentVoucher.document_id.in_(document_ids))
            await self._session.execute(delete(PaymentVoucher).where(or_(*voucher_conditions)))
        if payment_ids:
            await self._session.execute(
                delete(Payment).where(
                    Payment.id.in_(payment_ids),
                    Payment.payment_type == PaymentType.reversal,
                ),
            )
            await self._session.execute(delete(Payment).where(Payment.id.in_(payment_ids)))
        if document_ids:
            await self._session.execute(delete(Document).where(Document.id.in_(document_ids)))
        if phase_ids or sub_project_ids:
            revoke_conditions = []
            if phase_ids:
                revoke_conditions.append(RevokeRequest.phase_id.in_(phase_ids))
            if sub_project_ids:
                revoke_conditions.append(RevokeRequest.sub_project_id.in_(sub_project_ids))
            await self._session.execute(delete(RevokeRequest).where(or_(*revoke_conditions)))
        if phase_ids:
            await self._session.execute(
                delete(AcceptanceStep).where(AcceptanceStep.phase_id.in_(phase_ids)),
            )
        if task_ids:
            await self._session.execute(
                delete(TaskExecutor).where(TaskExecutor.task_id.in_(task_ids)),
            )
            await self._session.execute(delete(Task).where(Task.id.in_(task_ids)))
        if phase_ids:
            await self._session.execute(
                delete(PhaseHistory).where(PhaseHistory.phase_id.in_(phase_ids)),
            )
            await self._session.execute(delete(Phase).where(Phase.id.in_(phase_ids)))
        if sub_project_ids:
            await self._session.execute(
                delete(HandoverRequestProject).where(
                    HandoverRequestProject.sub_project_id.in_(sub_project_ids),
                ),
            )
            await self._session.execute(
                delete(SubProjectHandover).where(
                    SubProjectHandover.sub_project_id.in_(sub_project_ids),
                ),
            )
            await self._session.execute(
                delete(SubProjectMember).where(SubProjectMember.sub_project_id.in_(sub_project_ids)),
            )
            await self._session.execute(
                delete(ProjectReview).where(
                    or_(
                        ProjectReview.main_project_id.in_(main_project_ids),
                        ProjectReview.sub_project_id.in_(sub_project_ids),
                    ),
                ),
            )
            await self._session.execute(
                delete(SubProjectNoCounter).where(
                    SubProjectNoCounter.main_project_id.in_(main_project_ids),
                ),
            )
            await self._session.execute(
                delete(SubProject).where(SubProject.id.in_(sub_project_ids)),
            )
        await self._session.execute(delete(MainProject).where(MainProject.id.in_(main_project_ids)))

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def _ids(self, statement: Any) -> list[UUID]:
        result = await self._session.scalars(statement)
        return list(result.all())


class InMemoryArchiveRepository:
    def __init__(
        self,
        *,
        projects: Sequence[MainProject] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
        fail_on_delete: bool = False,
    ) -> None:
        self.projects = list(projects or [])
        self.sub_projects = list(sub_projects or [])
        self.archive_batches: list[ArchiveBatch] = []
        self.archive_main_projects: list[ArchiveMainProject] = []
        self.archive_sub_projects: list[ArchiveSubProject] = []
        self.fail_on_delete = fail_on_delete
        self._snapshot: tuple[
            list[MainProject],
            list[SubProject],
            list[ArchiveBatch],
            list[ArchiveMainProject],
            list[ArchiveSubProject],
        ] | None = None

    def begin(self) -> None:
        self._snapshot = (
            list(self.projects),
            list(self.sub_projects),
            list(self.archive_batches),
            list(self.archive_main_projects),
            list(self.archive_sub_projects),
        )

    async def list_candidate_projects(self, cutoff_at: datetime) -> list[MainProject]:
        return sorted(
            [
                project
                for project in self.projects
                if project.status == MainProjectStatus.closed
                and project.closed_at is not None
                and project.closed_at <= cutoff_at
                and not self._has_active_sub_project(project.id)
            ],
            key=lambda project: (
                project.closed_at or datetime.min.replace(tzinfo=UTC),
                project.project_no,
            ),
        )

    async def list_sub_projects_by_main_project_ids(
        self,
        main_project_ids: Sequence[UUID],
    ) -> list[SubProject]:
        ids = set(main_project_ids)
        return sorted(
            [
                sub_project
                for sub_project in self.sub_projects
                if sub_project.main_project_id in ids
            ],
            key=lambda sub_project: sub_project.project_no,
        )

    async def count_main_projects(self) -> int:
        return len(self.projects)

    async def list_batches(self, *, page: int, page_size: int) -> tuple[list[ArchiveBatch], int]:
        ordered = sorted(self.archive_batches, key=lambda batch: batch.created_at, reverse=True)
        start = (page - 1) * page_size
        return ordered[start : start + page_size], len(ordered)

    async def get_batch(self, batch_id: UUID) -> ArchiveBatch | None:
        return next((batch for batch in self.archive_batches if batch.id == batch_id), None)

    async def list_archive_main_projects(self, batch_id: UUID) -> list[ArchiveMainProject]:
        return sorted(
            [archive for archive in self.archive_main_projects if archive.batch_id == batch_id],
            key=lambda archive: archive.project_no,
        )

    async def list_archive_sub_projects(self, batch_id: UUID) -> list[ArchiveSubProject]:
        return sorted(
            [archive for archive in self.archive_sub_projects if archive.batch_id == batch_id],
            key=lambda archive: archive.project_no,
        )

    async def get_archive_main_project(
        self,
        archive_main_project_id: UUID,
    ) -> ArchiveMainProject | None:
        return next(
            (
                archive
                for archive in self.archive_main_projects
                if archive.id == archive_main_project_id
            ),
            None,
        )

    async def list_archive_sub_projects_for_main(
        self,
        *,
        batch_id: UUID,
        original_main_project_id: UUID,
    ) -> list[ArchiveSubProject]:
        return sorted(
            [
                archive
                for archive in self.archive_sub_projects
                if archive.batch_id == batch_id
                and archive.original_main_project_id == original_main_project_id
            ],
            key=lambda archive: archive.project_no,
        )

    async def main_project_no_exists(self, project_no: str) -> bool:
        return any(project.project_no == project_no for project in self.projects)

    async def sub_project_no_conflicts(self, project_nos: Sequence[str]) -> list[str]:
        candidates = set(project_nos)
        return sorted(
            [
                sub_project.project_no
                for sub_project in self.sub_projects
                if sub_project.project_no in candidates
            ],
        )

    def restore_main_project(
        self,
        project: MainProject,
        sub_projects: Sequence[SubProject],
    ) -> None:
        self.projects.append(project)
        self.sub_projects.extend(sub_projects)

    async def delete_archive_project_snapshots(
        self,
        *,
        archive_main_project_id: UUID,
        archive_sub_project_ids: Sequence[UUID],
    ) -> None:
        sub_project_ids = set(archive_sub_project_ids)
        self.archive_sub_projects = [
            archive for archive in self.archive_sub_projects if archive.id not in sub_project_ids
        ]
        self.archive_main_projects = [
            archive
            for archive in self.archive_main_projects
            if archive.id != archive_main_project_id
        ]

    def add_batch(self, batch: ArchiveBatch) -> None:
        self.archive_batches.append(batch)

    def add_archive_main_project(self, archive: ArchiveMainProject) -> None:
        self.archive_main_projects.append(archive)

    def add_archive_sub_project(self, archive: ArchiveSubProject) -> None:
        self.archive_sub_projects.append(archive)

    async def delete_project_graph(self, main_project_ids: Sequence[UUID]) -> None:
        if self.fail_on_delete:
            raise RuntimeError("delete failed")

        ids = set(main_project_ids)
        self.projects = [project for project in self.projects if project.id not in ids]
        self.sub_projects = [
            sub_project
            for sub_project in self.sub_projects
            if sub_project.main_project_id not in ids
        ]

    async def commit(self) -> None:
        self._snapshot = None

    async def rollback(self) -> None:
        if self._snapshot is None:
            return
        (
            self.projects,
            self.sub_projects,
            self.archive_batches,
            self.archive_main_projects,
            self.archive_sub_projects,
        ) = self._snapshot
        self._snapshot = None

    def _has_active_sub_project(self, main_project_id: UUID) -> bool:
        return any(
            sub_project.main_project_id == main_project_id
            and sub_project.status not in ARCHIVABLE_SUB_PROJECT_STATUSES
            for sub_project in self.sub_projects
        )


class ArchiveService:
    def __init__(
        self,
        *,
        repository: ArchiveRepository,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._now_provider = now_provider

    async def list_candidates(self) -> list[ArchiveCandidate]:
        projects = await self._repository.list_candidate_projects(self._cutoff_at())
        sub_projects = await self._repository.list_sub_projects_by_main_project_ids(
            [project.id for project in projects],
        )
        sub_projects_by_main_id = self._group_sub_projects(sub_projects)
        candidates: list[ArchiveCandidate] = []
        for project in projects:
            if project.closed_at is None:
                continue
            candidates.append(
                ArchiveCandidate(
                    main_project_id=project.id,
                    project_no=project.project_no,
                    name=project.name,
                    closed_at=project.closed_at,
                    sub_project_count=len(sub_projects_by_main_id[project.id]),
                ),
            )
        return candidates

    async def list_batches(self, *, page: int = 1, page_size: int = 20) -> ArchiveBatchPage:
        items, total = await self._repository.list_batches(page=page, page_size=page_size)
        return ArchiveBatchPage(items=items, page=page, page_size=page_size, total=total)

    async def get_batch_detail(self, batch_id: UUID) -> ArchiveBatchDetail:
        batch = await self._repository.get_batch(batch_id)
        if batch is None:
            raise ResourceNotFoundError("归档批次不存在")
        return ArchiveBatchDetail(
            batch=batch,
            main_projects=await self._repository.list_archive_main_projects(batch.id),
            sub_projects=await self._repository.list_archive_sub_projects(batch.id),
        )

    async def archive_eligible_projects(
        self,
        *,
        actor_id: UUID | None = None,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> ArchiveRunResult:
        self._repository.begin()
        try:
            started_at = self._now()
            before_count = await self._repository.count_main_projects()
            projects = await self._repository.list_candidate_projects(self._cutoff_at(started_at))
            project_ids = [project.id for project in projects]
            sub_projects = await self._repository.list_sub_projects_by_main_project_ids(project_ids)
            batch_id = uuid4()
            batch_no = self._batch_no(started_at)
            finished_at = self._now()
            duration_ms = self._duration_ms(started_at=started_at, finished_at=finished_at)
            batch = ArchiveBatch(
                id=batch_id,
                batch_no=batch_no,
                created_by_id=actor_id,
                status="completed",
                archived_main_project_count=len(projects),
                archived_sub_project_count=len(sub_projects),
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=finished_at,
                created_at=started_at,
                updated_at=finished_at,
            )
            self._repository.add_batch(batch)
            for project in projects:
                self._repository.add_archive_main_project(
                    ArchiveMainProject(
                        id=uuid4(),
                        batch_id=batch_id,
                        original_id=project.id,
                        project_no=project.project_no,
                        name=project.name,
                        status=project.status.value,
                        closed_at=project.closed_at,
                        snapshot=serialize_model(project),
                        archived_at=finished_at,
                        created_at=finished_at,
                        updated_at=finished_at,
                    ),
                )
            for sub_project in sub_projects:
                self._repository.add_archive_sub_project(
                    ArchiveSubProject(
                        id=uuid4(),
                        batch_id=batch_id,
                        original_id=sub_project.id,
                        original_main_project_id=sub_project.main_project_id,
                        project_no=sub_project.project_no,
                        name=sub_project.name,
                        status=sub_project.status.value,
                        closed_at=sub_project.closed_at,
                        snapshot=serialize_model(sub_project),
                        archived_at=finished_at,
                        created_at=finished_at,
                        updated_at=finished_at,
                    ),
                )

            await self._repository.delete_project_graph(project_ids)
            after_count = await self._repository.count_main_projects()
            await self._repository.commit()
            result = ArchiveRunResult(
                batch_id=batch_id,
                batch_no=batch_no,
                archived_main_project_count=len(projects),
                archived_sub_project_count=len(sub_projects),
                main_projects_before=before_count,
                main_projects_after=after_count,
                duration_ms=duration_ms,
            )
            self._record_audit(
                action="archive.create_batch",
                target_type="archive_batch",
                target_id=str(batch_id),
                actor_id=actor_id,
                before_state={},
                after_state=to_audit_state(result),
                audit_writer=audit_writer,
                audit_context=audit_context,
                extra={
                    "archived_main_project_ids": [str(project.id) for project in projects],
                    "archived_sub_project_count": len(sub_projects),
                },
            )
            return result
        except Exception:
            await self._repository.rollback()
            raise

    async def restore_main_project(
        self,
        *,
        actor: User,
        archive_main_project_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> MainProject:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()

        archive = await self._repository.get_archive_main_project(archive_main_project_id)
        if archive is None:
            raise ResourceNotFoundError("归档主项目不存在")
        if await self._repository.main_project_no_exists(archive.project_no):
            raise ResourceConflictError(
                "恢复主项目存在唯一键冲突",
                data={"fields": ["project_no"], "project_no": archive.project_no},
            )

        sub_archives = await self._repository.list_archive_sub_projects_for_main(
            batch_id=archive.batch_id,
            original_main_project_id=archive.original_id,
        )
        sub_project_conflicts = await self._repository.sub_project_no_conflicts(
            [sub_archive.project_no for sub_archive in sub_archives],
        )
        if sub_project_conflicts:
            raise ResourceConflictError(
                "恢复子项目存在唯一键冲突",
                data={
                    "fields": ["sub_project.project_no"],
                    "project_nos": sub_project_conflicts,
                },
            )
        project = main_project_from_snapshot(archive.snapshot)
        sub_projects = [
            sub_project_from_snapshot(sub_archive.snapshot) for sub_archive in sub_archives
        ]
        self._repository.begin()
        try:
            self._repository.restore_main_project(project, sub_projects)
            await self._repository.delete_archive_project_snapshots(
                archive_main_project_id=archive.id,
                archive_sub_project_ids=[sub_archive.id for sub_archive in sub_archives],
            )
            await self._repository.commit()
        except Exception:
            await self._repository.rollback()
            raise

        self._record_audit(
            action="archive.restore_main_project",
            target_type="main_project",
            target_id=str(project.id),
            actor_id=actor.id,
            before_state=archive.snapshot,
            after_state=serialize_model(project),
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={
                "archive_main_project_id": str(archive.id),
                "archive_batch_id": str(archive.batch_id),
                "restored_sub_project_count": len(sub_projects),
            },
        )
        return project

    def _cutoff_at(self, now: datetime | None = None) -> datetime:
        return (now or self._now()) - timedelta(days=ARCHIVE_RETENTION_DAYS)

    def _now(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @staticmethod
    def _group_sub_projects(sub_projects: Sequence[SubProject]) -> dict[UUID, list[SubProject]]:
        grouped: dict[UUID, list[SubProject]] = defaultdict(list)
        for sub_project in sub_projects:
            grouped[sub_project.main_project_id].append(sub_project)
        return grouped

    @staticmethod
    def _batch_no(now: datetime) -> str:
        return f"ARCH-{now:%Y%m%d}-{uuid4().hex[:8].upper()}"

    @staticmethod
    def _duration_ms(*, started_at: datetime, finished_at: datetime) -> int:
        return max(int((finished_at - started_at).total_seconds() * 1000), 0)

    @staticmethod
    def _record_audit(
        *,
        action: str,
        target_type: str,
        target_id: str,
        actor_id: UUID | None,
        before_state: dict[str, object],
        after_state: dict[str, object],
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
        extra: dict[str, object],
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor_id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id or actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                before_state=before_state,
                after_state=after_state,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra=extra,
                request_id=context.request_id,
            ),
        )


def serialize_model(model: object) -> dict[str, object | None]:
    table = cast(Any, model).__table__
    return {
        column.name: archive_json_value(getattr(model, column.name))
        for column in table.columns
    }


def archive_json_value(value: object | None) -> object | None:
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        enum_value = value.value
        if isinstance(enum_value, str | int | float | bool):
            return enum_value
        return str(enum_value)
    if isinstance(value, UUID | date | datetime | Decimal):
        return str(value)
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


def main_project_from_snapshot(snapshot: dict[str, object]) -> MainProject:
    return MainProject(
        id=_snapshot_uuid(snapshot, "id"),
        project_no=_snapshot_str(snapshot, "project_no"),
        name=_snapshot_str(snapshot, "name"),
        dept_id=_snapshot_uuid(snapshot, "dept_id"),
        status=MainProjectStatus(_snapshot_str(snapshot, "status")),
        total_budget=Decimal(_snapshot_str(snapshot, "total_budget")),
        expected_finish_date=_snapshot_date(snapshot, "expected_finish_date"),
        spent_amount=Decimal(_snapshot_str(snapshot, "spent_amount")),
        remark=_snapshot_optional_str(snapshot, "remark"),
        creator_id=_snapshot_optional_uuid(snapshot, "creator_id"),
        closed_at=_snapshot_optional_datetime(snapshot, "closed_at"),
        created_at=_snapshot_datetime(snapshot, "created_at"),
        updated_at=_snapshot_datetime(snapshot, "updated_at"),
    )


def sub_project_from_snapshot(snapshot: dict[str, object]) -> SubProject:
    return SubProject(
        id=_snapshot_uuid(snapshot, "id"),
        project_no=_snapshot_str(snapshot, "project_no"),
        name=_snapshot_str(snapshot, "name"),
        main_project_id=_snapshot_uuid(snapshot, "main_project_id"),
        dept_id=_snapshot_uuid(snapshot, "dept_id"),
        budget=Decimal(_snapshot_str(snapshot, "budget")),
        manager_id=_snapshot_uuid(snapshot, "manager_id"),
        creator_id=_snapshot_optional_uuid(snapshot, "creator_id"),
        status=SubProjectStatus(_snapshot_str(snapshot, "status")),
        plan_end_date=_snapshot_optional_date(snapshot, "plan_end_date"),
        actual_end_date=_snapshot_optional_date(snapshot, "actual_end_date"),
        spent_amount=Decimal(_snapshot_str(snapshot, "spent_amount")),
        remark=_snapshot_optional_str(snapshot, "remark"),
        closed_at=_snapshot_optional_datetime(snapshot, "closed_at"),
        created_at=_snapshot_datetime(snapshot, "created_at"),
        updated_at=_snapshot_datetime(snapshot, "updated_at"),
    )


def _snapshot_str(snapshot: dict[str, object], field: str) -> str:
    value = snapshot[field]
    return str(value)


def _snapshot_optional_str(snapshot: dict[str, object], field: str) -> str | None:
    value = snapshot.get(field)
    return None if value is None else str(value)


def _snapshot_uuid(snapshot: dict[str, object], field: str) -> UUID:
    return UUID(_snapshot_str(snapshot, field))


def _snapshot_optional_uuid(snapshot: dict[str, object], field: str) -> UUID | None:
    value = snapshot.get(field)
    return None if value is None else UUID(str(value))


def _snapshot_datetime(snapshot: dict[str, object], field: str) -> datetime:
    return datetime.fromisoformat(_snapshot_str(snapshot, field))


def _snapshot_optional_datetime(
    snapshot: dict[str, object],
    field: str,
) -> datetime | None:
    value = snapshot.get(field)
    return None if value is None else datetime.fromisoformat(str(value))


def _snapshot_date(snapshot: dict[str, object], field: str) -> date:
    return date.fromisoformat(_snapshot_str(snapshot, field))


def _snapshot_optional_date(snapshot: dict[str, object], field: str) -> date | None:
    value = snapshot.get(field)
    return None if value is None else date.fromisoformat(str(value))
