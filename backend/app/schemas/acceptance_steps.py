from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.acceptance_steps import AcceptanceStepStatus


class AcceptanceStepCreate(BaseModel):
    step_no: int
    step_name: str
    responsible_id: UUID
    plan_date: date | None = None
    description: str | None = None


class AcceptanceStepUpdate(BaseModel):
    status: AcceptanceStepStatus


class AcceptanceStepRead(BaseModel):
    id: UUID
    phase_id: UUID
    step_no: int
    step_name: str
    responsible_id: UUID
    plan_date: date | None
    description: str | None
    status: AcceptanceStepStatus
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AcceptanceStepListRead(BaseModel):
    items: list[AcceptanceStepRead]
    total: int
