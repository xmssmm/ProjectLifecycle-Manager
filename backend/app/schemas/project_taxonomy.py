from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project_taxonomy import ProjectTemplateScope


class ProjectCategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class ProjectTagCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=32)


class ProjectCategoryRead(ProjectCategoryCreate):
    id: UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectTagRead(ProjectTagCreate):
    id: UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectTemplateCreateFromProject(BaseModel):
    source_project_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    scope: ProjectTemplateScope = ProjectTemplateScope.private
    category_id: UUID | None = None
    tag_ids: list[UUID] = Field(default_factory=list, max_length=20)
    copy_phase_plan: bool = True
    copy_document_requirements: bool = True
    copy_task_checklist: bool = True


class ProjectTemplateInstantiate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dept_id: UUID | None = None
    expected_finish_date: date | None = None
    total_budget: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    remark: str | None = None


class ProjectTemplateRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    scope: ProjectTemplateScope
    owner_id: UUID
    owner_dept_id: UUID | None
    source_project_id: UUID | None
    source_project_no: str | None
    category_id: UUID | None
    project_type_id: UUID | None
    tag_ids: list[UUID]
    field_defaults: dict[str, Any]
    phase_snapshot: list[dict[str, Any]]
    document_requirements_snapshot: list[dict[str, Any]]
    default_task_checklist: list[dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
