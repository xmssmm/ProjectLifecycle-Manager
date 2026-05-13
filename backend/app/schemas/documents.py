from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.documents import DocumentScanStatus


class DocumentRead(BaseModel):
    id: UUID
    doc_no: str
    sub_project_id: UUID
    phase_id: UUID
    acceptance_step_id: UUID | None
    doc_type: str
    file_name: str
    display_name: str
    file_size: int
    version: int
    is_latest: bool
    is_deleted: bool
    scan_status: DocumentScanStatus
    scan_result: str | None
    scanned_at: datetime | None
    uploader_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListRead(BaseModel):
    items: list[DocumentRead]
    total: int
