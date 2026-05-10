from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.reports import ReportJobStatus, ReportType


class ReportCreate(BaseModel):
    report_type: ReportType
    parameters: dict[str, Any] = Field(default_factory=dict)


class ReportJobRead(BaseModel):
    id: UUID
    report_type: ReportType
    requested_by_id: UUID
    parameters: dict[str, Any]
    status: ReportJobStatus
    progress: int
    row_count: int
    available_formats: list[str]
    error_message: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
