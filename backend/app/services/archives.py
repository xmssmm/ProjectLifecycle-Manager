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

    async def archive_eligible_projects(self, *, actor_id: UUID | None = None) -> ArchiveRunResult:
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
            return ArchiveRunResult(
                batch_id=batch_id,
                batch_no=batch_no,
                archived_main_project_count=len(projects),
                archived_sub_project_count=len(sub_projects),
                main_projects_before=before_count,
                main_projects_after=after_count,
                duration_ms=duration_ms,
            )
        except Exception:
            await self._repository.rollback()
            raise

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
