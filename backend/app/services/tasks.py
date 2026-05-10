from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.models.phases import Phase
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole
from app.schemas.tasks import TaskCreate, TaskExecutorAssign, TaskUpdate
from app.services.notifications import NotificationService

VIEW_ALL_TASK_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)


class TaskRepository(Protocol):
    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def get_task(self, task_id: UUID) -> Task | None:
        ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def next_task_sequence(self, sub_project_id: UUID) -> int:
        ...

    async def list_tasks(
        self,
        *,
        actor: User,
        sub_project_id: UUID | None,
        assignee_id: UUID | None,
        status: TaskStatus | None,
    ) -> list[Task]:
        ...

    def add_task(self, task: Task) -> None:
        ...

    def add_executor(self, executor: TaskExecutor) -> None:
        ...

    async def delete_executor(self, executor: TaskExecutor) -> None:
        ...

    async def commit(self) -> None:
        ...


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.get(SubProject, sub_project_id)
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        phase = await self._session.get(Phase, phase_id)
        return phase if isinstance(phase, Phase) else None

    async def get_task(self, task_id: UUID) -> Task | None:
        task = await self._session.scalar(
            select(Task).options(selectinload(Task.executors)).where(Task.id == task_id),
        )
        return task if isinstance(task, Task) else None

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        member = await self._session.scalar(
            select(SubProjectMember).where(
                SubProjectMember.sub_project_id == sub_project_id,
                SubProjectMember.user_id == user_id,
            ),
        )
        return member if isinstance(member, SubProjectMember) else None

    async def next_task_sequence(self, sub_project_id: UUID) -> int:
        task_numbers = await self._session.scalars(
            select(Task.task_no).where(Task.sub_project_id == sub_project_id),
        )
        return next_sequence_from_task_numbers(task_numbers.all())

    async def list_tasks(
        self,
        *,
        actor: User,
        sub_project_id: UUID | None,
        assignee_id: UUID | None,
        status: TaskStatus | None,
    ) -> list[Task]:
        conditions = []
        if sub_project_id is not None:
            conditions.append(Task.sub_project_id == sub_project_id)
        if status is not None:
            conditions.append(Task.status == status)
        if assignee_id is not None:
            assignee_exists = (
                select(TaskExecutor.id)
                .where(
                    TaskExecutor.task_id == Task.id,
                    TaskExecutor.user_id == assignee_id,
                )
                .exists()
            )
            conditions.append(assignee_exists)
        if actor.role not in VIEW_ALL_TASK_ROLES:
            member_exists = (
                select(SubProjectMember.id)
                .where(
                    SubProjectMember.sub_project_id == Task.sub_project_id,
                    SubProjectMember.user_id == actor.id,
                )
                .exists()
            )
            manager_exists = (
                select(SubProject.id)
                .where(
                    SubProject.id == Task.sub_project_id,
                    SubProject.manager_id == actor.id,
                )
                .exists()
            )
            conditions.append(or_(manager_exists, member_exists))

        result = await self._session.scalars(
            select(Task)
            .options(selectinload(Task.executors))
            .where(*conditions)
            .order_by(Task.plan_end_date.asc(), Task.created_at.desc()),
        )
        return list(result.all())

    def add_task(self, task: Task) -> None:
        self._session.add(task)

    def add_executor(self, executor: TaskExecutor) -> None:
        self._session.add(executor)

    async def delete_executor(self, executor: TaskExecutor) -> None:
        await self._session.delete(executor)

    async def commit(self) -> None:
        await self._session.commit()


class InMemoryTaskRepository:
    def __init__(
        self,
        *,
        tasks: list[Task] | None = None,
        executors: list[TaskExecutor] | None = None,
        phases: list[Phase] | None = None,
        sub_projects: list[SubProject] | None = None,
        members: list[SubProjectMember] | None = None,
    ) -> None:
        self.tasks = list(tasks or [])
        self.executors = list(executors or [])
        self.phases = list(phases or [])
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])
        self._attach_executors()

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        return next((phase for phase in self.phases if phase.id == phase_id), None)

    async def get_task(self, task_id: UUID) -> Task | None:
        self._attach_executors()
        return next((task for task in self.tasks if task.id == task_id), None)

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        return next(
            (
                member
                for member in self.members
                if member.sub_project_id == sub_project_id and member.user_id == user_id
            ),
            None,
        )

    async def next_task_sequence(self, sub_project_id: UUID) -> int:
        task_numbers = [
            task.task_no for task in self.tasks if task.sub_project_id == sub_project_id
        ]
        return next_sequence_from_task_numbers(task_numbers)

    async def list_tasks(
        self,
        *,
        actor: User,
        sub_project_id: UUID | None,
        assignee_id: UUID | None,
        status: TaskStatus | None,
    ) -> list[Task]:
        self._attach_executors()
        tasks = list(self.tasks)
        if sub_project_id is not None:
            tasks = [task for task in tasks if task.sub_project_id == sub_project_id]
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        if assignee_id is not None:
            tasks = [
                task
                for task in tasks
                if any(executor.user_id == assignee_id for executor in task.executors)
            ]
        if actor.role not in VIEW_ALL_TASK_ROLES:
            visible_sub_projects = {
                sub_project.id
                for sub_project in self.sub_projects
                if sub_project.manager_id == actor.id
                or any(
                    member.sub_project_id == sub_project.id and member.user_id == actor.id
                    for member in self.members
                )
            }
            tasks = [task for task in tasks if task.sub_project_id in visible_sub_projects]
        return sorted(tasks, key=lambda task: (task.plan_end_date, task.created_at))

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)
        self.executors.extend(task.executors)

    def add_executor(self, executor: TaskExecutor) -> None:
        if executor not in self.executors:
            self.executors.append(executor)

    async def delete_executor(self, executor: TaskExecutor) -> None:
        if executor in self.executors:
            self.executors.remove(executor)
        for task in self.tasks:
            task.executors = [item for item in task.executors if item.id != executor.id]

    async def commit(self) -> None:
        self._attach_executors()

    def _attach_executors(self) -> None:
        executors_by_task: dict[UUID, list[TaskExecutor]] = {}
        for executor in self.executors:
            executors_by_task.setdefault(executor.task_id, []).append(executor)
        for task in self.tasks:
            assigned = executors_by_task.get(task.id)
            if assigned is not None:
                task.executors = assigned


class TaskService:
    def __init__(
        self,
        *,
        repository: TaskRepository,
        notification_service: NotificationService | None = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service
        self._today_provider = today_provider

    async def list_tasks(
        self,
        *,
        actor: User,
        sub_project_id: UUID | None = None,
        assignee: str | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        if assignee is not None and assignee != "me":
            raise ValidationFailedError("Only assignee=me is supported")
        if sub_project_id is not None:
            sub_project = await self._get_existing_sub_project(sub_project_id)
            await self._ensure_visible(actor, sub_project)
        return await self._repository.list_tasks(
            actor=actor,
            sub_project_id=sub_project_id,
            assignee_id=actor.id if assignee == "me" else None,
            status=status,
        )

    async def create_task(self, *, actor: User, payload: TaskCreate) -> Task:
        sub_project, phase = await self._get_existing_scope(
            sub_project_id=payload.sub_project_id,
            phase_id=payload.phase_id,
        )
        self._ensure_can_assign(actor, sub_project)
        assignments = await self._validate_assignments(
            sub_project_id=sub_project.id,
            assignments=payload.executors,
        )
        sequence = await self._repository.next_task_sequence(sub_project.id)
        now = datetime.now(UTC)
        task = Task(
            id=uuid4(),
            task_no=f"{sub_project.project_no}-T-{sequence:03d}",
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            name=payload.name,
            plan_end_date=payload.plan_end_date,
            status=TaskStatus.not_started,
            created_at=now,
            updated_at=now,
        )
        task.executors = [
            TaskExecutor(
                id=uuid4(),
                task_id=task.id,
                user_id=assignment.user_id,
                plan_end_date=assignment.plan_end_date,
                actual_end_date=None,
                status=TaskStatus.in_progress,
                created_at=now,
                updated_at=now,
            )
            for assignment in assignments
        ]
        task.status = self.aggregate_task_status(task)
        self._repository.add_task(task)
        await self._repository.commit()
        await self._send_task_assigned_notifications(
            task=task,
            receiver_ids=[assignment.user_id for assignment in assignments],
        )
        return task

    async def get_task(self, *, actor: User, task_id: UUID) -> Task:
        task = await self._get_existing_task(task_id)
        sub_project = await self._get_existing_sub_project(task.sub_project_id)
        await self._ensure_visible(actor, sub_project)
        return task

    async def update_task(self, *, actor: User, task_id: UUID, payload: TaskUpdate) -> Task:
        task = await self._get_existing_task(task_id)
        sub_project = await self._get_existing_sub_project(task.sub_project_id)
        self._ensure_can_assign(actor, sub_project)
        now = datetime.now(UTC)
        if payload.name is not None:
            task.name = payload.name
        if payload.plan_end_date is not None:
            task.plan_end_date = payload.plan_end_date

        new_receiver_ids: list[UUID] = []
        if payload.executors is not None:
            assignments = await self._validate_assignments(
                sub_project_id=sub_project.id,
                assignments=payload.executors,
            )
            existing_by_user = {executor.user_id: executor for executor in task.executors}
            assignment_user_ids = {assignment.user_id for assignment in assignments}
            updated_executors: list[TaskExecutor] = []
            for assignment in assignments:
                existing = existing_by_user.get(assignment.user_id)
                if existing is not None:
                    existing.plan_end_date = assignment.plan_end_date
                    existing.updated_at = now
                    updated_executors.append(existing)
                    continue
                new_executor = TaskExecutor(
                    id=uuid4(),
                    task_id=task.id,
                    user_id=assignment.user_id,
                    plan_end_date=assignment.plan_end_date,
                    actual_end_date=None,
                    status=TaskStatus.in_progress,
                    created_at=now,
                    updated_at=now,
                )
                self._repository.add_executor(new_executor)
                updated_executors.append(new_executor)
                new_receiver_ids.append(assignment.user_id)
            for executor in list(task.executors):
                if executor.user_id not in assignment_user_ids:
                    await self._repository.delete_executor(executor)
            task.executors = updated_executors
            task.status = self.aggregate_task_status(task)

        task.updated_at = now
        await self._repository.commit()
        await self._send_task_assigned_notifications(task=task, receiver_ids=new_receiver_ids)
        return task

    async def complete_task(self, *, actor: User, task_id: UUID) -> Task:
        task = await self._get_existing_task(task_id)
        executor = next(
            (item for item in task.executors if item.user_id == actor.id),
            None,
        )
        if executor is None:
            raise PermissionDeniedError()
        now = datetime.now(UTC)
        if executor.status != TaskStatus.completed:
            executor.status = TaskStatus.completed
            executor.actual_end_date = self._today_provider()
            executor.updated_at = now
            task.status = self.aggregate_task_status(task)
            task.updated_at = now
            await self._repository.commit()
        return task

    async def _get_existing_scope(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
    ) -> tuple[SubProject, Phase]:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        phase = await self._repository.get_phase(phase_id)
        if phase is None or phase.sub_project_id != sub_project.id:
            raise ResourceNotFoundError("Phase does not exist")
        return sub_project, phase

    async def _get_existing_sub_project(self, sub_project_id: UUID) -> SubProject:
        sub_project = await self._repository.get_sub_project(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        return sub_project

    async def _get_existing_task(self, task_id: UUID) -> Task:
        task = await self._repository.get_task(task_id)
        if task is None:
            raise ResourceNotFoundError("Task does not exist")
        return task

    async def _validate_assignments(
        self,
        *,
        sub_project_id: UUID,
        assignments: Sequence[TaskExecutorAssign],
    ) -> list[TaskExecutorAssign]:
        if not assignments:
            raise ValidationFailedError("At least one executor is required")
        seen: set[UUID] = set()
        validated: list[TaskExecutorAssign] = []
        for assignment in assignments:
            if assignment.user_id in seen:
                raise ValidationFailedError("Task executors must be unique")
            seen.add(assignment.user_id)
            member = await self._repository.get_member(
                sub_project_id=sub_project_id,
                user_id=assignment.user_id,
            )
            if member is None:
                raise BusinessException(
                    code=3003,
                    message="Task executor must be a sub project member",
                    status_code=409,
                    data={"user_id": str(assignment.user_id)},
                )
            validated.append(assignment)
        return validated

    async def _ensure_visible(self, actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_TASK_ROLES or sub_project.manager_id == actor.id:
            return
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=actor.id,
        )
        if member is not None:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_can_assign(actor: User, sub_project: SubProject) -> None:
        if actor.role == UserRole.admin:
            return
        if actor.role == UserRole.proj_leader and sub_project.manager_id == actor.id:
            return
        raise PermissionDeniedError()

    async def _send_task_assigned_notifications(
        self,
        *,
        task: Task,
        receiver_ids: Sequence[UUID],
    ) -> None:
        if self._notification_service is None or not receiver_ids:
            return
        await self._notification_service.send(
            scenario="task_assigned",
            receivers=receiver_ids,
            source_id=task.id,
            payload={
                "task_id": str(task.id),
                "task_no": task.task_no,
                "sub_project_id": str(task.sub_project_id),
                "phase_id": str(task.phase_id),
            },
        )

    @staticmethod
    def aggregate_task_status(task: Task) -> TaskStatus:
        statuses = [executor.status for executor in task.executors]
        if statuses and all(status == TaskStatus.completed for status in statuses):
            return TaskStatus.completed
        if any(status == TaskStatus.overdue for status in statuses):
            return TaskStatus.overdue
        if any(status == TaskStatus.in_progress for status in statuses):
            return TaskStatus.in_progress
        return TaskStatus.not_started


def next_sequence_from_task_numbers(task_numbers: Sequence[str]) -> int:
    max_sequence = 0
    for task_no in task_numbers:
        try:
            sequence = int(task_no.rsplit("-T-", maxsplit=1)[1])
        except (IndexError, ValueError):
            continue
        max_sequence = max(max_sequence, sequence)
    return max_sequence + 1
