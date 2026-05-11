from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError
from app.models.main_projects import MainProject
from app.models.payments import Payment
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole

CACHE_TTL_SECONDS = 300
DashboardPayload = dict[str, Any]


@dataclass(frozen=True)
class DashboardSnapshot:
    users: Sequence[User]
    main_projects: Sequence[MainProject]
    sub_projects: Sequence[SubProject]
    sub_project_members: Sequence[SubProjectMember]
    tasks: Sequence[Task]
    task_executors: Sequence[TaskExecutor]
    phases: Sequence[Phase]
    payments: Sequence[Payment]


class DashboardCache(Protocol):
    async def get(self, key: str) -> DashboardPayload | None:
        ...

    async def set(self, key: str, payload: DashboardPayload, *, ttl_seconds: int) -> None:
        ...


class DashboardRepository(Protocol):
    async def load_snapshot(self) -> DashboardSnapshot:
        ...


class InMemoryDashboardCache:
    def __init__(self) -> None:
        self.values: dict[str, DashboardPayload] = {}
        self.last_key: str | None = None
        self.last_ttl_seconds: int | None = None

    async def get(self, key: str) -> DashboardPayload | None:
        self.last_key = key
        return self.values.get(key)

    async def set(self, key: str, payload: DashboardPayload, *, ttl_seconds: int) -> None:
        self.last_key = key
        self.last_ttl_seconds = ttl_seconds
        self.values[key] = payload


class RedisDashboardCache:
    def __init__(self, redis_url: str | None = None, *, redis_client: Redis | None = None) -> None:
        if redis_client is None and redis_url is None:
            raise ValueError("redis_url or redis_client is required")
        self._client = redis_client or Redis.from_url(str(redis_url), decode_responses=True)

    async def get(self, key: str) -> DashboardPayload | None:
        raw_value = await self._client.get(key)
        if raw_value is None:
            return None
        decoded = json.loads(raw_value)
        return decoded if isinstance(decoded, dict) else None

    async def set(self, key: str, payload: DashboardPayload, *, ttl_seconds: int) -> None:
        await self._client.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False))


class InMemoryDashboardRepository:
    def __init__(self, snapshot: DashboardSnapshot) -> None:
        self._snapshot = snapshot
        self.load_count = 0

    async def load_snapshot(self) -> DashboardSnapshot:
        self.load_count += 1
        return self._snapshot


class SqlAlchemyDashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_snapshot(self) -> DashboardSnapshot:
        users = list((await self._session.scalars(select(User))).all())
        main_projects = list((await self._session.scalars(select(MainProject))).all())
        sub_projects = list((await self._session.scalars(select(SubProject))).all())
        sub_project_members = list((await self._session.scalars(select(SubProjectMember))).all())
        tasks = list((await self._session.scalars(select(Task))).all())
        task_executors = list((await self._session.scalars(select(TaskExecutor))).all())
        phases = list((await self._session.scalars(select(Phase))).all())
        payments = list((await self._session.scalars(select(Payment))).all())
        return DashboardSnapshot(
            users=users,
            main_projects=main_projects,
            sub_projects=sub_projects,
            sub_project_members=sub_project_members,
            tasks=tasks,
            task_executors=task_executors,
            phases=phases,
            payments=payments,
        )


class DashboardService:
    def __init__(
        self,
        *,
        repository: DashboardRepository,
        cache: DashboardCache,
        today_provider: Callable[[], date] = date.today,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._today_provider = today_provider
        self._now_provider = now_provider

    async def get_dashboard(self, *, actor: User, role_scope: UserRole) -> DashboardPayload:
        if actor.role != role_scope and actor.role != UserRole.admin:
            raise PermissionDeniedError("Cannot access another role dashboard")

        cache_key = f"dashboard:{role_scope.value}:{actor.id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        snapshot = await self._repository.load_snapshot()
        dashboard = self._build_dashboard(actor=actor, role_scope=role_scope, snapshot=snapshot)
        await self._cache.set(cache_key, dashboard, ttl_seconds=CACHE_TTL_SECONDS)
        return dashboard

    def _base_payload(self, role_scope: UserRole) -> DashboardPayload:
        return {
            "role_scope": role_scope.value,
            "generated_at": self._now_provider().isoformat(),
            "cache_ttl_seconds": CACHE_TTL_SECONDS,
            "metrics": {},
            "charts": {},
            "lists": {},
        }

    def _build_dashboard(
        self,
        *,
        actor: User,
        role_scope: UserRole,
        snapshot: DashboardSnapshot,
    ) -> DashboardPayload:
        builders = {
            UserRole.admin: self._build_admin_dashboard,
            UserRole.dept_manager: self._build_dept_manager_dashboard,
            UserRole.finance_manager: self._build_finance_dashboard,
            UserRole.proj_leader: self._build_project_leader_dashboard,
            UserRole.proj_member: self._build_project_member_dashboard,
        }
        return builders[role_scope](actor, snapshot)

    def _build_admin_dashboard(self, _actor: User, snapshot: DashboardSnapshot) -> DashboardPayload:
        payload = self._base_payload(UserRole.admin)
        over_budget = self._over_budget_sub_projects(snapshot.sub_projects)
        payload["metrics"] = {
            "total_main_projects": len(snapshot.main_projects),
            "total_users": len(snapshot.users),
            "over_budget_sub_projects": len(over_budget),
            "due_soon_tasks": len(self._due_soon_tasks(snapshot.tasks)),
            "api_error_rate_source": "prometheus",
        }
        payload["charts"] = {
            "main_project_status": self._status_chart(
                (project.status for project in snapshot.main_projects),
            ),
            "sub_project_status": self._status_chart(
                (project.status for project in snapshot.sub_projects),
            ),
        }
        payload["lists"] = {"over_budget_sub_projects": self._sub_project_list(over_budget)}
        return payload

    def _build_dept_manager_dashboard(
        self,
        _actor: User,
        snapshot: DashboardSnapshot,
    ) -> DashboardPayload:
        today = self._today_provider()
        over_budget = self._over_budget_sub_projects(snapshot.sub_projects)
        payload = self._base_payload(UserRole.dept_manager)
        payload["metrics"] = {
            "main_projects": len(snapshot.main_projects),
            "current_month_new_projects": sum(
                1
                for project in snapshot.main_projects
                if project.created_at.year == today.year and project.created_at.month == today.month
            ),
            "over_budget_sub_projects": len(over_budget),
        }
        payload["charts"] = {
            "main_project_status": self._status_chart(
                (project.status for project in snapshot.main_projects),
            ),
            "department_project_counts": self._department_project_counts(snapshot.main_projects),
        }
        payload["lists"] = {"over_budget_sub_projects": self._sub_project_list(over_budget)}
        return payload

    def _build_finance_dashboard(
        self,
        _actor: User,
        snapshot: DashboardSnapshot,
    ) -> DashboardPayload:
        today = self._today_provider()
        current_month_payments = [
            payment
            for payment in snapshot.payments
            if payment.payment_date.year == today.year and payment.payment_date.month == today.month
        ]
        total_budget = sum(
            (project.total_budget for project in snapshot.main_projects),
            Decimal("0"),
        )
        total_paid = sum((payment.amount for payment in snapshot.payments), Decimal("0"))
        payload = self._base_payload(UserRole.finance_manager)
        payload["metrics"] = {
            "current_month_payment_total": self._money(
                sum((payment.amount for payment in current_month_payments), Decimal("0")),
            ),
            "total_paid": self._money(total_paid),
            "total_budget": self._money(total_budget),
        }
        payload["charts"] = {
            "paid_vs_budget": [
                {"label": "paid", "value": self._money(total_paid)},
                {"label": "budget", "value": self._money(total_budget)},
            ],
        }
        payload["lists"] = {
            "sub_project_payment_ranking": self._sub_project_payment_ranking(snapshot),
            "unpaid_sub_projects": [
                {"id": str(project.id), "name": project.name, "status": project.status.value}
                for project in snapshot.sub_projects
                if project.spent_amount == Decimal("0.00")
            ],
        }
        return payload

    def _build_project_leader_dashboard(
        self,
        actor: User,
        snapshot: DashboardSnapshot,
    ) -> DashboardPayload:
        managed_sub_projects = [
            project for project in snapshot.sub_projects if project.manager_id == actor.id
        ]
        managed_ids = {project.id for project in managed_sub_projects}
        due_tasks = self._due_soon_tasks(snapshot.tasks, sub_project_ids=managed_ids)
        phases_to_promote = [
            phase
            for phase in snapshot.phases
            if phase.sub_project_id in managed_ids and phase.status == PhaseStatus.in_progress
        ]
        payload = self._base_payload(UserRole.proj_leader)
        payload["metrics"] = {
            "managed_sub_projects": len(managed_sub_projects),
            "due_or_overdue_tasks": len(due_tasks),
            "phases_to_promote": len(phases_to_promote),
        }
        payload["charts"] = {
            "sub_project_status": self._status_chart(
                (project.status for project in managed_sub_projects),
            ),
        }
        payload["lists"] = {
            "phases_to_promote": [
                {
                    "id": str(phase.id),
                    "sub_project_id": str(phase.sub_project_id),
                    "phase_no": phase.phase_no,
                    "name": phase.name,
                }
                for phase in phases_to_promote
            ],
        }
        return payload

    def _build_project_member_dashboard(
        self,
        actor: User,
        snapshot: DashboardSnapshot,
    ) -> DashboardPayload:
        visible_sub_project_ids = {
            member.sub_project_id
            for member in snapshot.sub_project_members
            if member.user_id == actor.id
        }
        visible_sub_projects = [
            project for project in snapshot.sub_projects if project.id in visible_sub_project_ids
        ]
        todo_task_ids = {
            executor.task_id
            for executor in snapshot.task_executors
            if executor.user_id == actor.id and executor.status != TaskStatus.completed
        }
        todo_tasks = [task for task in snapshot.tasks if task.id in todo_task_ids]
        payload = self._base_payload(UserRole.proj_member)
        payload["metrics"] = {
            "todo_tasks": len(todo_tasks),
            "participating_sub_projects": len(visible_sub_projects),
        }
        payload["charts"] = {
            "todo_tasks_by_due_date": self._due_date_chart(todo_tasks),
        }
        payload["lists"] = {
            "participating_sub_projects": [
                {"id": str(project.id), "name": project.name, "status": project.status.value}
                for project in sorted(
                    visible_sub_projects,
                    key=lambda item: item.updated_at,
                    reverse=True,
                )
            ],
        }
        return payload

    def _due_soon_tasks(
        self,
        tasks: Sequence[Task],
        *,
        sub_project_ids: set[UUID] | None = None,
    ) -> list[Task]:
        deadline = self._today_provider() + timedelta(days=7)
        return [
            task
            for task in tasks
            if task.status != TaskStatus.completed
            and (task.status == TaskStatus.overdue or task.plan_end_date <= deadline)
            and (sub_project_ids is None or task.sub_project_id in sub_project_ids)
        ]

    @staticmethod
    def _over_budget_sub_projects(sub_projects: Sequence[SubProject]) -> list[SubProject]:
        return [project for project in sub_projects if project.spent_amount > project.budget]

    @staticmethod
    def _status_chart(statuses: Iterable[object]) -> list[dict[str, object]]:
        counts: dict[str, int] = {}
        for status in statuses:
            value = getattr(status, "value", str(status))
            counts[value] = counts.get(value, 0) + 1
        return [{"label": label, "value": counts[label]} for label in sorted(counts)]

    @staticmethod
    def _department_project_counts(projects: Sequence[MainProject]) -> list[dict[str, object]]:
        counts: dict[str, int] = {}
        for project in projects:
            key = str(project.dept_id)
            counts[key] = counts.get(key, 0) + 1
        return [{"label": label, "value": counts[label]} for label in sorted(counts)]

    @staticmethod
    def _sub_project_list(projects: Sequence[SubProject]) -> list[dict[str, object]]:
        return [
            {
                "id": str(project.id),
                "name": project.name,
                "status": project.status.value,
                "budget": DashboardService._money(project.budget),
                "spent_amount": DashboardService._money(project.spent_amount),
            }
            for project in projects
        ]

    @staticmethod
    def _sub_project_payment_ranking(snapshot: DashboardSnapshot) -> list[dict[str, object]]:
        projects = sorted(snapshot.sub_projects, key=lambda item: item.spent_amount, reverse=True)
        return [
            {
                "id": str(project.id),
                "name": project.name,
                "spent_amount": DashboardService._money(project.spent_amount),
            }
            for project in projects[:5]
        ]

    @staticmethod
    def _due_date_chart(tasks: Sequence[Task]) -> list[dict[str, object]]:
        counts: dict[str, int] = {}
        for task in tasks:
            key = task.plan_end_date.isoformat()
            counts[key] = counts.get(key, 0) + 1
        return [{"label": label, "value": counts[label]} for label in sorted(counts)]

    @staticmethod
    def _money(value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01")))
