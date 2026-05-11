from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class DocumentSearchResultRead(BaseModel):
    document_id: UUID
    file_name: str
    doc_type: str
    sub_project_id: UUID
    sub_project_no: str
    sub_project_name: str
    phase_id: UUID
    phase_name: str
    snippet: str


class DocumentSearchResultsRead(BaseModel):
    items: list[DocumentSearchResultRead]
    total: int
