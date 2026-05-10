from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.main_projects import ProjectReviewDecision
from app.models.sub_projects import SubProjectMemberRole, SubProjectStatus


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


class SubProjectReviewUpdate(BaseModel):
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


class SubProjectReviewRequest(BaseModel):
    decision: ProjectReviewDecision
    review_comment: str | None = None
    updates: SubProjectReviewUpdate | None = None
    confirm_over_budget: bool = False
    over_budget_reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class SubProjectTerminateRequest(BaseModel):
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]

    model_config = ConfigDict(extra="forbid")


class SubProjectMemberCreate(BaseModel):
    user_id: UUID

    model_config = ConfigDict(extra="forbid")


class SubProjectHandoverRequest(BaseModel):
    to_user_id: UUID
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]

    model_config = ConfigDict(extra="forbid")


class SubProjectBatchHandoverItem(SubProjectHandoverRequest):
    sub_project_id: UUID


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


class SubProjectMemberRead(BaseModel):
    id: UUID
    sub_project_id: UUID
    user_id: UUID
    role_in_project: SubProjectMemberRole
    joined_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubProjectMemberListRead(BaseModel):
    items: list[SubProjectMemberRead]
    total: int
