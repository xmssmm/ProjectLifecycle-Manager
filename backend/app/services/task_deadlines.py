from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole, UserStatus
from app.services.notifications import NotificationService, current_business_date
from app.services.tasks import TaskService

ACTIVE_DEADLINE_STATUSES = (TaskStatus.not_started, TaskStatus.in_progress)


@dataclass(frozen=True)
class TaskDeadlineScanResult:
    due_today: int
    marked_overdue: int
    due_notifications: int
    overdue_notifications: int
    overdue_escalations: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class TaskDeadlineRepository(Protocol):
    async def list_due_today_executors(self, target_date: date) -> list[TaskExecutor]:
        ...

    async def list_overdue_executors(self, target_date: date) -> list[TaskExecutor]:
        ...

    async def list_admin_ids(self) -> list[UUID]:
        ...

    async def commit(self) -> None:
        ...


class SqlAlchemyTaskDeadlineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_due_today_executors(self, target_date: date) -> list[TaskExecutor]:
        result = await self._session.scalars(
            select(TaskExecutor)
            .options(selectinload(TaskExecutor.task).selectinload(Task.executors))
            .where(
                TaskExecutor.plan_end_date == target_date,
                TaskExecutor.status.in_(ACTIVE_DEADLINE_STATUSES),
            ),
        )
        return list(result.all())

    async def list_overdue_executors(self, target_date: date) -> list[TaskExecutor]:
        result = await self._session.scalars(
            select(TaskExecutor)
            .options(selectinload(TaskExecutor.task).selectinload(Task.executors))
            .where(
                TaskExecutor.plan_end_date < target_date,
                TaskExecutor.status.in_(ACTIVE_DEADLINE_STATUSES),
            ),
        )
        return list(result.all())

    async def list_admin_ids(self) -> list[UUID]:
        result = await self._session.scalars(
            select(User.id).where(
                User.role == UserRole.admin,
                User.status == UserStatus.active,
            ),
        )
        return list(result.all())

    async def commit(self) -> None:
        await self._session.commit()


class InMemoryTaskDeadlineRepository:
    def __init__(
        self,
        *,
        executors: Sequence[TaskExecutor],
        users: Sequence[User],
    ) -> None:
        self.executors = list(executors)
        self.users = list(users)

    async def list_due_today_executors(self, target_date: date) -> list[TaskExecutor]:
        return [
            executor
            for executor in self.executors
            if executor.plan_end_date == target_date and executor.status in ACTIVE_DEADLINE_STATUSES
        ]

    async def list_overdue_executors(self, target_date: date) -> list[TaskExecutor]:
        return [
            executor
            for executor in self.executors
            if executor.plan_end_date < target_date and executor.status in ACTIVE_DEADLINE_STATUSES
        ]

    async def list_admin_ids(self) -> list[UUID]:
        return [
            user.id
            for user in self.users
            if user.role == UserRole.admin and user.status == UserStatus.active
        ]

    async def commit(self) -> None:
        return None


class TaskDeadlineService:
    def __init__(
        self,
        *,
        repository: TaskDeadlineRepository,
        notification_service: NotificationService,
        business_date_provider: Callable[[], date] = current_business_date,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service
        self._business_date_provider = business_date_provider

    async def scan_deadlines(self) -> TaskDeadlineScanResult:
        business_date = self._business_date_provider()
        due_today_executors = await self._repository.list_due_today_executors(business_date)
        overdue_executors = await self._repository.list_overdue_executors(business_date)

        due_notifications = await self._notify_due_today(
            business_date=business_date,
            executors=due_today_executors,
        )
        marked_overdue = await self._mark_overdue(overdue_executors)
        overdue_notifications = await self._notify_overdue(
            business_date=business_date,
            executors=overdue_executors,
        )
        overdue_escalations = await self._notify_escalations(
            business_date=business_date,
            executors=overdue_executors,
        )

        return TaskDeadlineScanResult(
            due_today=len(due_today_executors),
            marked_overdue=marked_overdue,
            due_notifications=due_notifications,
            overdue_notifications=overdue_notifications,
            overdue_escalations=overdue_escalations,
        )

    async def _mark_overdue(self, executors: Sequence[TaskExecutor]) -> int:
        if not executors:
            return 0

        now = datetime.now(UTC)
        for executor in executors:
            executor.status = TaskStatus.overdue
            executor.updated_at = now
            executor.task.status = TaskService.aggregate_task_status(executor.task)
            executor.task.updated_at = now
        await self._repository.commit()
        return len(executors)

    async def _notify_due_today(
        self,
        *,
        business_date: date,
        executors: Sequence[TaskExecutor],
    ) -> int:
        sent_count = 0
        for executor in executors:
            sent = await self._notification_service.send(
                scenario="task_due_today",
                receivers=[executor.user_id],
                source_id=executor.id,
                payload=self._build_payload(
                    executor=executor,
                    business_date=business_date,
                ),
            )
            sent_count += len(sent)
        return sent_count

    async def _notify_overdue(
        self,
        *,
        business_date: date,
        executors: Sequence[TaskExecutor],
    ) -> int:
        sent_count = 0
        for executor in executors:
            sent = await self._notification_service.send(
                scenario="task_overdue",
                receivers=[executor.user_id],
                source_id=executor.id,
                payload=self._build_payload(
                    executor=executor,
                    business_date=business_date,
                ),
            )
            sent_count += len(sent)
        return sent_count

    async def _notify_escalations(
        self,
        *,
        business_date: date,
        executors: Sequence[TaskExecutor],
    ) -> int:
        admin_ids = await self._repository.list_admin_ids()
        if not admin_ids:
            return 0

        sent_count = 0
        for executor in executors:
            if self._days_overdue(executor=executor, business_date=business_date) < 7:
                continue
            sent = await self._notification_service.send(
                scenario="task_overdue_escalation",
                receivers=admin_ids,
                source_id=executor.id,
                payload=self._build_payload(
                    executor=executor,
                    business_date=business_date,
                ),
            )
            sent_count += len(sent)
        return sent_count

    def _build_payload(self, *, executor: TaskExecutor, business_date: date) -> dict[str, object]:
        return {
            "task_id": str(executor.task_id),
            "task_no": executor.task.task_no,
            "executor_id": str(executor.id),
            "user_id": str(executor.user_id),
            "plan_end_date": executor.plan_end_date.isoformat(),
            "days_overdue": self._days_overdue(
                executor=executor,
                business_date=business_date,
            ),
        }

    @staticmethod
    def _days_overdue(*, executor: TaskExecutor, business_date: date) -> int:
        return max((business_date - executor.plan_end_date).days, 0)
