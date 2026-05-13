from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import inspect
from sqlalchemy.orm import LoaderCallableStatus

from app.models.main_projects import MainProject, MainProjectStatus, ProjectReviewDecision
from app.models.phases import PhaseStatus
from app.models.sub_projects import SubProjectStatus


def _loaded_relationship(instance: object, name: str) -> object | None:
    inspected = inspect(instance)
    assert inspected is not None
    value = inspected.attrs[name].loaded_value
    return None if value is LoaderCallableStatus.NO_VALUE else value


class MainProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dept_id: UUID
    total_budget: Decimal = Field(ge=Decimal("0.00"), max_digits=15, decimal_places=2)
    expected_finish_date: date
    remark: str | None = None

    model_config = ConfigDict(extra="forbid")


class MainProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dept_id: UUID | None = None
    total_budget: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        max_digits=15,
        decimal_places=2,
    )
    expected_finish_date: date | None = None
    remark: str | None = None

    model_config = ConfigDict(extra="forbid")


class MainProjectReviewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dept_id: UUID | None = None
    total_budget: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        max_digits=15,
        decimal_places=2,
    )
    expected_finish_date: date | None = None
    remark: str | None = None

    model_config = ConfigDict(extra="forbid")


class MainProjectReviewRequest(BaseModel):
    decision: ProjectReviewDecision
    review_comment: str | None = None
    updates: MainProjectReviewUpdate | None = None

    model_config = ConfigDict(extra="forbid")


class MainProjectRead(BaseModel):
    id: UUID
    project_no: str
    name: str
    dept_id: UUID
    status: MainProjectStatus
    total_budget: Decimal
    expected_finish_date: date
    spent_amount: Decimal
    remark: str | None
    creator_id: UUID | None
    created_at: datetime
    updated_at: datetime
    dept_name: str | None = None
    creator_name: str | None = None
    remaining_amount: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_business_summary(cls, data: Any) -> Any:
        if not isinstance(data, MainProject):
            return data
        department = _loaded_relationship(data, "department")
        creator = _loaded_relationship(data, "creator")
        return {
            "id": data.id,
            "project_no": data.project_no,
            "name": data.name,
            "dept_id": data.dept_id,
            "status": data.status,
            "total_budget": data.total_budget,
            "expected_finish_date": data.expected_finish_date,
            "spent_amount": data.spent_amount,
            "remark": data.remark,
            "creator_id": data.creator_id,
            "created_at": data.created_at,
            "updated_at": data.updated_at,
            "dept_name": getattr(department, "name", None),
            "creator_name": getattr(creator, "username", None),
            "remaining_amount": data.total_budget - data.spent_amount,
        }


class MainProjectListRead(BaseModel):
    items: list[MainProjectRead]
    total: int
    page: int
    page_size: int


class ProjectProgressFunnelSubProjectRead(BaseModel):
    id: UUID
    project_no: str
    name: str
    status: SubProjectStatus
    phase_status: PhaseStatus


class ProjectProgressFunnelItemRead(BaseModel):
    phase_no: int
    code: str
    name: str
    sub_project_count: int
    sub_projects: list[ProjectProgressFunnelSubProjectRead]


class ProjectProgressFunnelRead(BaseModel):
    main_project_id: UUID
    total_sub_projects: int
    items: list[ProjectProgressFunnelItemRead]
