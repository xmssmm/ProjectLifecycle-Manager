from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Table, UniqueConstraint

from app.models.base import Base
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.schemas.tasks import TaskExecutorRead, TaskRead


def test_task_status_enum_matches_requirements() -> None:
    assert [status.value for status in TaskStatus] == [
        "not_started",
        "in_progress",
        "overdue",
        "completed",
    ]


def test_task_tables_have_required_columns_and_constraints() -> None:
    assert "tasks" in Base.metadata.tables
    assert "task_executors" in Base.metadata.tables

    task_columns = set(Task.__table__.c.keys())
    executor_columns = set(TaskExecutor.__table__.c.keys())

    assert {
        "id",
        "task_no",
        "sub_project_id",
        "phase_id",
        "name",
        "plan_end_date",
        "status",
        "created_at",
        "updated_at",
    }.issubset(task_columns)
    assert {
        "id",
        "task_id",
        "user_id",
        "plan_end_date",
        "actual_end_date",
        "status",
        "created_at",
        "updated_at",
    }.issubset(executor_columns)

    task_table = Task.__table__
    executor_table = TaskExecutor.__table__
    assert isinstance(task_table, Table)
    assert isinstance(executor_table, Table)
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("task_id", "user_id")
        for constraint in executor_table.constraints
    )


def test_task_models_serialize_from_orm_instances() -> None:
    now = datetime.now(UTC)
    task_id = uuid4()
    sub_project_id = uuid4()
    phase_id = uuid4()
    user_id = uuid4()
    task = Task(
        id=task_id,
        task_no="Z-2026-0001-ZX-001-T-001",
        sub_project_id=sub_project_id,
        phase_id=phase_id,
        name="整理会议纪要",
        plan_end_date=date(2026, 5, 20),
        status=TaskStatus.in_progress,
        created_at=now,
        updated_at=now,
    )
    executor = TaskExecutor(
        id=uuid4(),
        task_id=task_id,
        user_id=user_id,
        plan_end_date=date(2026, 5, 19),
        actual_end_date=None,
        status=TaskStatus.not_started,
        created_at=now,
        updated_at=now,
    )

    task_payload = TaskRead.model_validate(task).model_dump()
    executor_payload = TaskExecutorRead.model_validate(executor).model_dump()

    assert task_payload["id"] == task_id
    assert task_payload["sub_project_id"] == sub_project_id
    assert task_payload["status"] == TaskStatus.in_progress
    assert executor_payload["task_id"] == task_id
    assert executor_payload["user_id"] == user_id


def test_task_schema_uuid_fields_are_typed() -> None:
    assert TaskRead.model_fields["sub_project_id"].annotation is UUID
    assert TaskRead.model_fields["phase_id"].annotation is UUID
    assert TaskExecutorRead.model_fields["actual_end_date"].annotation == date | None
