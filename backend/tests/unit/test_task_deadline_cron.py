from __future__ import annotations

from datetime import UTC, date, datetime
from importlib import import_module
from types import ModuleType
from uuid import uuid4

import pytest

from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole, UserStatus
from app.services.notifications import InMemoryNotificationRepository, NotificationService


def load_deadline_module() -> ModuleType:
    try:
        return import_module("app.services.task_deadlines")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.services.task_deadlines is required: {exc}")


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


def make_task(*, sequence: int, plan_end_date: date) -> Task:
    now = datetime.now(UTC)
    return Task(
        id=uuid4(),
        task_no=f"Z-2026-0001-ZX-001-T-{sequence:03d}",
        sub_project_id=uuid4(),
        phase_id=uuid4(),
        name=f"Task {sequence}",
        plan_end_date=plan_end_date,
        status=TaskStatus.in_progress,
        created_at=now,
        updated_at=now,
    )


def make_executor(
    task: Task,
    user: User,
    *,
    plan_end_date: date,
    status: TaskStatus = TaskStatus.in_progress,
) -> TaskExecutor:
    now = datetime.now(UTC)
    executor = TaskExecutor(
        id=uuid4(),
        task_id=task.id,
        user_id=user.id,
        plan_end_date=plan_end_date,
        actual_end_date=None,
        status=status,
        created_at=now,
        updated_at=now,
    )
    executor.task = task
    task.executors = [executor]
    return executor


@pytest.mark.asyncio
async def test_deadline_scan_marks_overdue_aggregates_and_notifies() -> None:
    deadline_module = load_deadline_module()
    today = date(2026, 5, 10)
    due_user = make_user(UserRole.proj_member, username="due")
    late_user = make_user(UserRole.proj_member, username="late")
    escalated_user = make_user(UserRole.proj_member, username="escalated")
    admin = make_user(UserRole.admin, username="admin")
    due_task = make_task(sequence=1, plan_end_date=today)
    late_task = make_task(sequence=2, plan_end_date=date(2026, 5, 9))
    escalated_task = make_task(sequence=3, plan_end_date=date(2026, 5, 2))
    completed_task = make_task(sequence=4, plan_end_date=date(2026, 5, 1))
    due_executor = make_executor(due_task, due_user, plan_end_date=today)
    late_executor = make_executor(late_task, late_user, plan_end_date=date(2026, 5, 9))
    escalated_executor = make_executor(
        escalated_task,
        escalated_user,
        plan_end_date=date(2026, 5, 2),
    )
    completed_executor = make_executor(
        completed_task,
        late_user,
        plan_end_date=date(2026, 5, 1),
        status=TaskStatus.completed,
    )
    completed_task.status = TaskStatus.completed
    notification_repository = InMemoryNotificationRepository()
    service = deadline_module.TaskDeadlineService(
        repository=deadline_module.InMemoryTaskDeadlineRepository(
            executors=[due_executor, late_executor, escalated_executor, completed_executor],
            users=[admin],
        ),
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: today,
        ),
        business_date_provider=lambda: today,
    )

    result = await service.scan_deadlines()

    assert result.due_today == 1
    assert result.marked_overdue == 2
    assert result.overdue_escalations == 1
    assert due_executor.status == TaskStatus.in_progress
    assert late_executor.status == TaskStatus.overdue
    assert escalated_executor.status == TaskStatus.overdue
    assert late_task.status == TaskStatus.overdue
    assert escalated_task.status == TaskStatus.overdue
    assert completed_executor.status == TaskStatus.completed
    assert completed_task.status == TaskStatus.completed
    assert [
        (item.scenario, item.receiver_id, item.source_id)
        for item in notification_repository.notifications
    ] == [
        ("task_due_today", due_user.id, str(due_executor.id)),
        ("task_overdue", late_user.id, str(late_executor.id)),
        ("task_overdue", escalated_user.id, str(escalated_executor.id)),
        ("task_overdue_escalation", admin.id, str(escalated_executor.id)),
    ]
    escalation_payload = notification_repository.notifications[-1].payload
    assert escalation_payload["days_overdue"] == 8


@pytest.mark.asyncio
async def test_deadline_scan_deduplicates_repeated_runs_but_keeps_distinct_tasks() -> None:
    deadline_module = load_deadline_module()
    today = date(2026, 5, 10)
    member = make_user(UserRole.proj_member, username="member")
    first_task = make_task(sequence=1, plan_end_date=today)
    second_task = make_task(sequence=2, plan_end_date=today)
    first_executor = make_executor(first_task, member, plan_end_date=today)
    second_executor = make_executor(second_task, member, plan_end_date=today)
    notification_repository = InMemoryNotificationRepository()
    service = deadline_module.TaskDeadlineService(
        repository=deadline_module.InMemoryTaskDeadlineRepository(
            executors=[first_executor, second_executor],
            users=[],
        ),
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: today,
        ),
        business_date_provider=lambda: today,
    )

    first_result = await service.scan_deadlines()
    second_result = await service.scan_deadlines()

    assert first_result.due_today == 2
    assert second_result.due_today == 2
    assert len(notification_repository.notifications) == 2
    assert {item.source_id for item in notification_repository.notifications} == {
        str(first_executor.id),
        str(second_executor.id),
    }


def test_celery_beat_schedules_deadline_scan_at_0900_business_time() -> None:
    from app.tasks.celery_app import create_celery_app
    from app.tasks.task_names import TASK_DEADLINE_SCAN_TASK_NAME

    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["task-deadline-scan-daily-0900"]
    assert celery_app.conf.timezone == "Asia/Shanghai"
    assert schedule["task"] == TASK_DEADLINE_SCAN_TASK_NAME
    assert "0 9 * * *" in str(schedule["schedule"])
