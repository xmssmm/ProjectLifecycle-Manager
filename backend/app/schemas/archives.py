from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ArchiveCandidateRead(BaseModel):
    main_project_id: UUID
    project_no: str
    name: str
    closed_at: datetime
    sub_project_count: int


class ArchiveRunResultRead(BaseModel):
    batch_id: UUID
    batch_no: str
    archived_main_project_count: int
    archived_sub_project_count: int
    main_projects_before: int
    main_projects_after: int
    duration_ms: int
