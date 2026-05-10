from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.phases import PhaseDocRequirement, PhaseStatus, ProcurementType


class PhaseRead(BaseModel):
    id: UUID
    sub_project_id: UUID
    phase_no: int
    code: str
    name: str
    status: PhaseStatus
    enter_at: datetime | None
    finish_at: datetime | None
    procurement_type: ProcurementType | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhaseListRead(BaseModel):
    items: list[PhaseRead]
    total: int


class PhaseDocTemplateRead(BaseModel):
    id: UUID
    phase_no: int
    doc_type: str
    requirement: PhaseDocRequirement
    qty_rule: str
    procurement_type: ProcurementType | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhaseRequiredDocumentRead(BaseModel):
    doc_type: str
    requirement: PhaseDocRequirement
    qty_rule: str
    procurement_type: ProcurementType | None

    model_config = ConfigDict(from_attributes=True)


class PhaseUploadedDocumentRead(BaseModel):
    id: UUID
    doc_type: str
    file_name: str
    file_size: int
    version: int
    uploader_id: UUID
    uploaded_at: datetime


class PhaseCompletionRead(BaseModel):
    required_total: int
    uploaded_total: int
    missing_doc_types: list[str]


class PhaseDetailRead(PhaseRead):
    required_documents: list[PhaseRequiredDocumentRead]
    uploaded_documents: list[PhaseUploadedDocumentRead]
    completion: PhaseCompletionRead


class PhasePromotionRead(BaseModel):
    phase: PhaseRead
    activated_phase: PhaseRead | None


class PhaseHistoryRead(BaseModel):
    id: UUID
    phase_id: UUID
    from_status: PhaseStatus | None
    to_status: PhaseStatus
    changed_by_id: UUID | None
    changed_at: datetime
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
