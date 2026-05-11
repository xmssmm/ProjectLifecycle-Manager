from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.main_projects import MainProjectStatus


class ProjectImportRowErrorRead(BaseModel):
    row_number: int
    field: str
    message: str
    value: str | None = None


class ProjectImportCreatedProjectRead(BaseModel):
    id: UUID
    project_no: str
    name: str
    dept_id: UUID
    status: MainProjectStatus

    model_config = ConfigDict(from_attributes=True)


class ProjectImportResultRead(BaseModel):
    batch_no: str
    total_rows: int
    success_count: int
    failure_count: int
    duration_ms: int
    errors: list[ProjectImportRowErrorRead]
    created_projects: list[ProjectImportCreatedProjectRead]

