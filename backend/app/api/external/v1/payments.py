from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.external.v1.deps import ExternalApiContext, require_external_permission
from app.core.db import get_db_session
from app.core.responses import success_response
from app.models.payments import Payment

router = APIRouter(tags=["external-api"])


class ExternalPaymentRead(BaseModel):
    id: UUID
    payment_no: str
    sub_project_id: UUID
    amount: Decimal
    payment_date: date
    payment_type: str
    created_at: datetime
    updated_at: datetime


class ExternalPaymentListRead(BaseModel):
    items: list[ExternalPaymentRead]
    total: int


class ExternalPaymentReader(Protocol):
    async def list_payments(self) -> Sequence[ExternalPaymentRead | dict[str, object]]:
        ...


class SqlAlchemyExternalPaymentReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_payments(self) -> list[ExternalPaymentRead]:
        result = await self._session.scalars(select(Payment).order_by(Payment.created_at.desc()))
        return [
            ExternalPaymentRead(
                id=payment.id,
                payment_no=payment.payment_no,
                sub_project_id=payment.sub_project_id,
                amount=payment.amount,
                payment_date=payment.payment_date,
                payment_type=payment.payment_type.value,
                created_at=payment.created_at,
                updated_at=payment.updated_at,
            )
            for payment in result.all()
        ]


async def get_external_payment_reader(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExternalPaymentReader:
    return SqlAlchemyExternalPaymentReader(session)


@router.get("/payments")
async def list_payments(
    reader: Annotated[ExternalPaymentReader, Depends(get_external_payment_reader)],
    _context: Annotated[ExternalApiContext, Depends(require_external_permission("payments:read"))],
) -> dict[str, object]:
    items = [ExternalPaymentRead.model_validate(item) for item in await reader.list_payments()]
    payload = ExternalPaymentListRead(items=items, total=len(items))
    return success_response(payload.model_dump(mode="json"))
