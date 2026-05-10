from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.tasks import TaskStatus


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

    model_config = ConfigDict(from_attributes=True)
