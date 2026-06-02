from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payments import PaymentType


class PaymentVoucherRead(BaseModel):
    id: UUID
    payment_id: UUID
    document_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentVoucherDocumentRead(BaseModel):
    id: UUID
    doc_type: str
    file_name: str
    display_name: str
    file_size: int
    version: int
    is_deleted: bool
    uploader_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentVoucherWithDocumentRead(PaymentVoucherRead):
    document: PaymentVoucherDocumentRead


class PaymentRead(BaseModel):
    id: UUID
    payment_no: str
    sub_project_id: UUID
    amount: Decimal
    payment_date: date
    remark: str | None
    payment_type: PaymentType
    reverses_payment_id: UUID | None
    operator_id: UUID | None
    vouchers: list[PaymentVoucherWithDocumentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentListRead(BaseModel):
    items: list[PaymentRead]
    page: int
    page_size: int
    total: int
