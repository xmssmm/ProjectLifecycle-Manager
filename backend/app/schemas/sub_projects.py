from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.sub_projects import SubProjectStatus


class SubProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    main_project_id: UUID
    dept_id: UUID
    budget: Decimal = Field(ge=Decimal("0.00"), max_digits=15, decimal_places=2)
    plan_end_date: date | None = None
    remark: str | None = None

    model_config = ConfigDict(extra="forbid")


class SubProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dept_id: UUID | None = None
    budget: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        max_digits=15,
        decimal_places=2,
    )
    plan_end_date: date | None = None
    remark: str | None = None

    model_config = ConfigDict(extra="forbid")


class SubProjectRead(BaseModel):
    id: UUID
    project_no: str
    name: str
    main_project_id: UUID
    dept_id: UUID
    budget: Decimal
    manager_id: UUID
    creator_id: UUID | None
    status: SubProjectStatus
    plan_end_date: date | None
    actual_end_date: date | None
    spent_amount: Decimal
    remark: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubProjectListRead(BaseModel):
    items: list[SubProjectRead]
    total: int
    page: int
    page_size: int
