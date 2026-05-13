from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import inspect
from sqlalchemy.orm import LoaderCallableStatus

from app.models.main_projects import ProjectReviewDecision
from app.models.sub_projects import SubProject, SubProjectMemberRole, SubProjectStatus


def _loaded_relationship(instance: object, name: str) -> object | None:
    inspected = inspect(instance)
    assert inspected is not None
    value = inspected.attrs[name].loaded_value
    return None if value is LoaderCallableStatus.NO_VALUE else value


class SubProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    main_project_id: UUID
    dept_id: UUID
    budget: Decimal = Field(ge=Decimal("0.00"), max_digits=15, decimal_places=2)
    plan_end_date: date | None = None
    workflow_template_version_id: UUID | None = None
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
    workflow_template_version_id: UUID | None
    actual_end_date: date | None
    spent_amount: Decimal
    remark: str | None
    created_at: datetime
    updated_at: datetime
    dept_name: str | None = None
    main_project_name: str | None = None
    manager_name: str | None = None
    remaining_amount: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_business_summary(cls, data: Any) -> Any:
        if not isinstance(data, SubProject):
            return data
        department = _loaded_relationship(data, "department")
        main_project = _loaded_relationship(data, "main_project")
        manager = _loaded_relationship(data, "manager")
        return {
            "id": data.id,
            "project_no": data.project_no,
            "name": data.name,
            "main_project_id": data.main_project_id,
            "dept_id": data.dept_id,
            "budget": data.budget,
            "manager_id": data.manager_id,
            "creator_id": data.creator_id,
            "status": data.status,
            "plan_end_date": data.plan_end_date,
            "workflow_template_version_id": data.workflow_template_version_id,
            "actual_end_date": data.actual_end_date,
            "spent_amount": data.spent_amount,
            "remark": data.remark,
            "created_at": data.created_at,
            "updated_at": data.updated_at,
            "dept_name": getattr(department, "name", None),
            "main_project_name": getattr(main_project, "name", None),
            "manager_name": getattr(manager, "username", None),
            "remaining_amount": data.budget - data.spent_amount,
        }


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


class SubProjectHandoverRead(BaseModel):
    id: UUID
    sub_project_id: UUID
    from_user_id: UUID
    to_user_id: UUID
    reason: str
    operator_id: UUID
    operated_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubProjectHandoverListRead(BaseModel):
    items: list[SubProjectHandoverRead]
    total: int
    page: int
    page_size: int
