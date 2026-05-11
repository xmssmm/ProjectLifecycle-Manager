from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.exports import DatabaseExportJobStatus


class DatabaseExportJobRead(BaseModel):
    id: UUID
    requested_by_id: UUID
    status: DatabaseExportJobStatus
    progress: int
    table_count: int
    row_count: int
    download_url: str | None
    manifest: dict[str, object]
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
