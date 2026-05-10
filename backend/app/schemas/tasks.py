from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.tasks import TaskStatus


class TaskExecutorAssign(BaseModel):
    user_id: UUID
    plan_end_date: date

    model_config = ConfigDict(extra="forbid")


class TaskCreate(BaseModel):
    sub_project_id: UUID
    phase_id: UUID
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    plan_end_date: date
    executors: list[TaskExecutorAssign] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class TaskUpdate(BaseModel):
    name: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ] = None
    plan_end_date: date | None = None
    executors: list[TaskExecutorAssign] | None = Field(default=None, min_length=1)

    model_config = ConfigDict(extra="forbid")


class TaskExecutorRead(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    plan_end_date: date
    actual_end_date: date | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskRead(BaseModel):
    id: UUID
    task_no: str
    sub_project_id: UUID
    phase_id: UUID
    name: str
    plan_end_date: date
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    executors: list[TaskExecutorRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TaskListRead(BaseModel):
    items: list[TaskRead]
    total: int
