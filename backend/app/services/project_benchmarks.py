from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import floor
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.main_projects import MainProject
from app.models.phases import Phase
from app.models.project_taxonomy import ProjectTemplate
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.tasks import Task, TaskStatus
from app.models.users import User, UserRole

READY_STATUS = "ready"
INSUFFICIENT_SAMPLE_STATUS = "insufficient_sample"


@dataclass(frozen=True)
class BenchmarkProjectSnapshot:
    id: UUID
    category_id: UUID | None
    closed_at: datetime | None
    created_at: datetime
    creator_id: UUID | None
    dept_id: UUID
    expected_finish_date: date
    participant_user_ids: frozenset[UUID]
    phase_durations_days: tuple[float, ...]
    project_no: str
    project_type_id: UUID | None
    spent_amount: Decimal
    tag_ids: tuple[UUID, ...]
    task_count: int
    overdue_task_count: int
    total_budget: Decimal
    updated_at: datetime

    def with_cycle_days(self, cycle_days: int) -> BenchmarkProjectSnapshot:
        return BenchmarkProjectSnapshot(
            id=self.id,
            category_id=self.category_id,
            closed_at=self.closed_at,
            created_at=(self.closed_at or self.updated_at) - timedelta(days=cycle_days),
            creator_id=self.creator_id,
            dept_id=self.dept_id,
            expected_finish_date=self.expected_finish_date,
            participant_user_ids=self.participant_user_ids,
            phase_durations_days=self.phase_durations_days,
            project_no=self.project_no,
            project_type_id=self.project_type_id,
            spent_amount=self.spent_amount,
            tag_ids=self.tag_ids,
            task_count=self.task_count,
            overdue_task_count=self.overdue_task_count,
            total_budget=self.total_budget,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class BenchmarkMetric:
    key: str
    label: str
    unit: str
    current_value: float | None
    sample_count: int
    average: float | None
    p50: float | None
    p90: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "average": self.average,
            "current_value": self.current_value,
            "key": self.key,
            "label": self.label,
            "p50": self.p50,
            "p90": self.p90,
            "sample_count": self.sample_count,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class ProjectBenchmarkResult:
    project_id: UUID
    sample_count: int
    scope: Mapping[str, object]
    status: str
    metrics: tuple[BenchmarkMetric, ...]

    def metric(self, key: str) -> BenchmarkMetric:
        return next(metric for metric in self.metrics if metric.key == key)

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": [metric.to_dict() for metric in self.metrics],
            "project_id": str(self.project_id),
            "sample_count": self.sample_count,
            "scope": self.scope,
            "status": self.status,
        }


class ProjectBenchmarkRepository(Protocol):
    async def get_project(self, project_id: UUID) -> BenchmarkProjectSnapshot | None: ...

    async def list_projects(self) -> list[BenchmarkProjectSnapshot]: ...


class InMemoryProjectBenchmarkRepository:
    def __init__(self, projects: Sequence[BenchmarkProjectSnapshot]) -> None:
        self._projects = list(projects)

    async def get_project(self, project_id: UUID) -> BenchmarkProjectSnapshot | None:
        return next((project for project in self._projects if project.id == project_id), None)

    async def list_projects(self) -> list[BenchmarkProjectSnapshot]:
        return list(self._projects)


class SqlAlchemyProjectBenchmarkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project(self, project_id: UUID) -> BenchmarkProjectSnapshot | None:
        snapshots = await self.list_projects()
        return next((project for project in snapshots if project.id == project_id), None)

    async def list_projects(self) -> list[BenchmarkProjectSnapshot]:
        projects = list((await self._session.scalars(select(MainProject))).all())
        project_ids = [project.id for project in projects]
        if not project_ids:
            return []

        sub_projects = list(
            (
                await self._session.scalars(
                    select(SubProject).where(SubProject.main_project_id.in_(project_ids)),
                )
            ).all(),
        )
        sub_project_ids = [sub_project.id for sub_project in sub_projects]
        phases = list(
            (
                await self._session.scalars(
                    select(Phase).where(Phase.sub_project_id.in_(sub_project_ids)),
                )
            ).all(),
        )
        tasks = list(
            (
                await self._session.scalars(
                    select(Task).where(Task.sub_project_id.in_(sub_project_ids)),
                )
            ).all(),
        )
        members = list(
            (
                await self._session.scalars(
                    select(SubProjectMember).where(
                        SubProjectMember.sub_project_id.in_(sub_project_ids),
                    ),
                )
            ).all(),
        )
        templates = list(
            (
                await self._session.scalars(
                    select(ProjectTemplate).where(ProjectTemplate.source_project_id.in_(project_ids)),
                )
            ).all(),
        )
        return [
            self._build_snapshot(
                project=project,
                sub_projects=sub_projects,
                phases=phases,
                tasks=tasks,
                members=members,
                templates=templates,
            )
            for project in projects
        ]

    @staticmethod
    def _build_snapshot(
        *,
        project: MainProject,
        sub_projects: Sequence[SubProject],
        phases: Sequence[Phase],
        tasks: Sequence[Task],
        members: Sequence[SubProjectMember],
        templates: Sequence[ProjectTemplate],
    ) -> BenchmarkProjectSnapshot:
        project_sub_projects = [
            sub_project for sub_project in sub_projects if sub_project.main_project_id == project.id
        ]
        sub_project_ids = {sub_project.id for sub_project in project_sub_projects}
        project_phases = [phase for phase in phases if phase.sub_project_id in sub_project_ids]
        project_tasks = [task for task in tasks if task.sub_project_id in sub_project_ids]
        project_members = [
            member for member in members if member.sub_project_id in sub_project_ids
        ]
        project_templates = [
            template for template in templates if template.source_project_id == project.id
        ]
        category_id = next(
            (template.category_id for template in project_templates if template.category_id),
            None,
        )
        tag_ids = tuple(
            {
                UUID(tag_id)
                for template in project_templates
                for tag_id in template.tag_ids
            },
        )
        participant_ids = {
            sub_project.manager_id for sub_project in project_sub_projects if sub_project.manager_id
        } | {member.user_id for member in project_members}
        phase_durations = tuple(
            (phase.finish_at - phase.enter_at).total_seconds() / 86400
            for phase in project_phases
            if phase.enter_at is not None and phase.finish_at is not None
        )
        overdue_count = sum(1 for task in project_tasks if task.status == TaskStatus.overdue)
        return BenchmarkProjectSnapshot(
            id=project.id,
            category_id=category_id,
            closed_at=project.closed_at,
            created_at=project.created_at,
            creator_id=project.creator_id,
            dept_id=project.dept_id,
            expected_finish_date=project.expected_finish_date,
            participant_user_ids=frozenset(participant_ids),
            phase_durations_days=phase_durations,
            project_no=project.project_no,
            project_type_id=project.project_type_id,
            spent_amount=project.spent_amount,
            tag_ids=tag_ids,
            task_count=len(project_tasks),
            overdue_task_count=overdue_count,
            total_budget=project.total_budget,
            updated_at=project.updated_at,
        )


class ProjectBenchmarkService:
    def __init__(
        self,
        *,
        repository: ProjectBenchmarkRepository,
        min_sample_size: int = 5,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._min_sample_size = min_sample_size
        self._now_provider = now_provider

    async def analyze_project(self, *, actor: User, project_id: UUID) -> ProjectBenchmarkResult:
        target = await self._repository.get_project(project_id)
        if target is None:
            raise ResourceNotFoundError("Project does not exist")
        if not self._can_view(actor, target):
            raise PermissionDeniedError()

        projects = await self._repository.list_projects()
        samples = [
            project
            for project in projects
            if project.id != target.id
            if self._can_view(actor, project)
            if self._same_scope(target, project)
        ]
        status = (
            READY_STATUS
            if len(samples) >= self._min_sample_size
            else INSUFFICIENT_SAMPLE_STATUS
        )
        return ProjectBenchmarkResult(
            metrics=tuple(self._build_metrics(target=target, samples=samples, status=status)),
            project_id=target.id,
            sample_count=len(samples),
            scope=self._scope(target),
            status=status,
        )

    def _build_metrics(
        self,
        *,
        target: BenchmarkProjectSnapshot,
        samples: Sequence[BenchmarkProjectSnapshot],
        status: str,
    ) -> list[BenchmarkMetric]:
        definitions = [
            ("cycle_days", "周期", "天", self._cycle_days),
            ("budget_variance_percent", "预算偏差", "%", self._budget_variance_percent),
            ("phase_stay_days", "环节停留", "天", self._phase_stay_days),
            ("task_overdue_rate", "任务逾期", "%", self._task_overdue_rate),
        ]
        metrics: list[BenchmarkMetric] = []
        for key, label, unit, extractor in definitions:
            values = [value for sample in samples if (value := extractor(sample)) is not None]
            current_value = extractor(target)
            metrics.append(
                BenchmarkMetric(
                    key=key,
                    label=label,
                    unit=unit,
                    current_value=current_value,
                    sample_count=len(values),
                    average=self._average(values) if status == READY_STATUS else None,
                    p50=self._percentile(values, 50) if status == READY_STATUS else None,
                    p90=self._percentile(values, 90) if status == READY_STATUS else None,
                ),
            )
        return metrics

    def _cycle_days(self, project: BenchmarkProjectSnapshot) -> float | None:
        end_at = project.closed_at or project.updated_at or self._now_provider()
        return max((end_at - project.created_at).total_seconds() / 86400, 0)

    @staticmethod
    def _budget_variance_percent(project: BenchmarkProjectSnapshot) -> float | None:
        if project.total_budget == 0:
            return None
        return float((project.spent_amount - project.total_budget) / project.total_budget * 100)

    @staticmethod
    def _phase_stay_days(project: BenchmarkProjectSnapshot) -> float | None:
        if not project.phase_durations_days:
            return None
        return sum(project.phase_durations_days) / len(project.phase_durations_days)

    @staticmethod
    def _task_overdue_rate(project: BenchmarkProjectSnapshot) -> float | None:
        if project.task_count == 0:
            return None
        return project.overdue_task_count / project.task_count * 100

    @staticmethod
    def _average(values: Sequence[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _percentile(values: Sequence[float], percentile: int) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * percentile / 100
        lower = floor(position)
        upper = min(lower + 1, len(ordered) - 1)
        if lower == upper:
            return ordered[lower]
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @staticmethod
    def _same_scope(
        target: BenchmarkProjectSnapshot,
        sample: BenchmarkProjectSnapshot,
    ) -> bool:
        if sample.dept_id != target.dept_id:
            return False
        if target.project_type_id is not None and sample.project_type_id != target.project_type_id:
            return False
        if target.category_id is not None and sample.category_id != target.category_id:
            return False
        if target.tag_ids and not set(target.tag_ids).intersection(sample.tag_ids):
            return False
        return True

    @staticmethod
    def _can_view(actor: User, project: BenchmarkProjectSnapshot) -> bool:
        if actor.role == UserRole.admin:
            return True
        if actor.role in {UserRole.dept_manager, UserRole.finance_manager}:
            return actor.dept_id is not None and actor.dept_id == project.dept_id
        if actor.id == project.creator_id:
            return True
        return actor.id in project.participant_user_ids

    @staticmethod
    def _scope(project: BenchmarkProjectSnapshot) -> dict[str, object]:
        return {
            "category_id": str(project.category_id) if project.category_id else None,
            "dept_id": str(project.dept_id),
            "project_type_id": str(project.project_type_id) if project.project_type_id else None,
            "tag_ids": [str(tag_id) for tag_id in project.tag_ids],
        }
