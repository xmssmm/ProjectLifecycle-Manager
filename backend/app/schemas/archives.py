from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class ArchiveBatchRead(BaseModel):
    id: UUID
    batch_no: str
    created_by_id: UUID | None
    status: str
    archived_main_project_count: int
    archived_sub_project_count: int
    duration_ms: int
    started_at: datetime
    finished_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArchiveMainProjectRead(BaseModel):
    id: UUID
    batch_id: UUID
    original_id: UUID
    project_no: str
    name: str
    status: str
    closed_at: datetime | None
    snapshot: dict[str, object]
    archived_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArchiveSubProjectRead(BaseModel):
    id: UUID
    batch_id: UUID
    original_id: UUID
    original_main_project_id: UUID
    project_no: str
    name: str
    status: str
    closed_at: datetime | None
    snapshot: dict[str, object]
    archived_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArchiveBatchListRead(BaseModel):
    items: list[ArchiveBatchRead]
    page: int
    page_size: int
    total: int


class ArchiveBatchDetailRead(BaseModel):
    batch: ArchiveBatchRead
    main_projects: list[ArchiveMainProjectRead]
    sub_projects: list[ArchiveSubProjectRead]
