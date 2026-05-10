from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.exceptions import ValidationFailedError
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.payments import Payment, PaymentType
from app.models.users import User
from app.schemas.payments import PaymentRead
from app.services.notifications import NotificationService, SqlAlchemyNotificationRepository
from app.services.payments import (
    PaymentService,
    PaymentVoucherUpload,
    SqlAlchemyPaymentRepository,
)
from app.storage.factory import create_storage_backend

router = APIRouter(prefix="/sub-projects/{sub_project_id}/payments", tags=["payments"])


def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PaymentService:
    return PaymentService(
        repository=SqlAlchemyPaymentRepository(session),
        storage=create_storage_backend(settings),
        max_file_size_bytes=settings.max_upload_size_bytes,
        notification_service=NotificationService(
            repository=SqlAlchemyNotificationRepository(session),
        ),
    )


def serialize_payment(payment: Payment) -> dict[str, object]:
    return PaymentRead.model_validate(payment).model_dump(mode="json")


@router.post("")
async def create_payment(
    sub_project_id: UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    current_user: Annotated[User, Depends(require_permission("payment.create"))],
    files: Annotated[list[UploadFile] | None, File(alias="files")] = None,
    amount: Annotated[Decimal | None, Form()] = None,
    payment_date: Annotated[date | None, Form()] = None,
    remark: Annotated[str | None, Form()] = None,
    payment_type: Annotated[PaymentType, Form()] = PaymentType.normal,
    reverses_payment_id: Annotated[UUID | None, Form()] = None,
    confirm_over_budget: Annotated[bool, Form()] = False,
    over_budget_reason: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    if payment_type == PaymentType.reversal:
        if reverses_payment_id is None:
            raise ValidationFailedError("Original payment is required")
        payment = await service.reverse_payment(
            actor=current_user,
            sub_project_id=sub_project_id,
            reverses_payment_id=reverses_payment_id,
            remark=remark,
        )
        return success_response(serialize_payment(payment))

    if amount is None:
        raise ValidationFailedError("Payment amount is required")
    if payment_date is None:
        raise ValidationFailedError("Payment date is required")

    voucher_files = [
        PaymentVoucherUpload(
            file_name=file.filename or "",
            content_type=file.content_type,
            content=await file.read(),
        )
        for file in files or []
    ]
    payment = await service.create_payment(
        actor=current_user,
        sub_project_id=sub_project_id,
        amount=amount,
        payment_date=payment_date,
        remark=remark,
        confirm_over_budget=confirm_over_budget,
        over_budget_reason=over_budget_reason,
        voucher_files=voucher_files,
    )
    return success_response(serialize_payment(payment))
