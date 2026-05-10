from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Table, UniqueConstraint

from app.models.base import Base
from app.models.payments import Payment, PaymentType, PaymentVoucher
from app.schemas.payments import PaymentRead, PaymentVoucherRead


def test_payment_type_enum_matches_requirements() -> None:
    assert [payment_type.value for payment_type in PaymentType] == ["normal", "reversal"]


def test_payment_tables_have_required_columns_and_constraints() -> None:
    assert "payments" in Base.metadata.tables
    assert "payment_vouchers" in Base.metadata.tables

    payment_columns = set(Payment.__table__.c.keys())
    voucher_columns = set(PaymentVoucher.__table__.c.keys())

    assert {
        "id",
        "payment_no",
        "sub_project_id",
        "amount",
        "payment_date",
        "remark",
        "payment_type",
        "reverses_payment_id",
        "operator_id",
        "created_at",
        "updated_at",
    }.issubset(payment_columns)
    assert {
        "id",
        "payment_id",
        "document_id",
        "created_at",
        "updated_at",
    }.issubset(voucher_columns)

    payment_table = Payment.__table__
    voucher_table = PaymentVoucher.__table__
    assert isinstance(payment_table, Table)
    assert isinstance(voucher_table, Table)
    assert any(
        foreign_key.parent.name == "reverses_payment_id"
        for foreign_key in payment_table.foreign_keys
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("document_id",)
        for constraint in voucher_table.constraints
    )


def test_payment_models_serialize_from_orm_instances() -> None:
    now = datetime.now(UTC)
    payment_id = uuid4()
    sub_project_id = uuid4()
    operator_id = uuid4()
    document_id = uuid4()
    payment = Payment(
        id=payment_id,
        payment_no="Z-2026-0001-ZX-001-PAY-001",
        sub_project_id=sub_project_id,
        amount=Decimal("1200.50"),
        payment_date=date(2026, 5, 10),
        remark="首付款",
        payment_type=PaymentType.normal,
        reverses_payment_id=None,
        operator_id=operator_id,
        created_at=now,
        updated_at=now,
    )
    voucher = PaymentVoucher(
        id=uuid4(),
        payment_id=payment_id,
        document_id=document_id,
        created_at=now,
        updated_at=now,
    )

    payment_payload = PaymentRead.model_validate(payment).model_dump()
    voucher_payload = PaymentVoucherRead.model_validate(voucher).model_dump()

    assert payment_payload["id"] == payment_id
    assert payment_payload["sub_project_id"] == sub_project_id
    assert payment_payload["amount"] == Decimal("1200.50")
    assert payment_payload["payment_type"] == PaymentType.normal
    assert voucher_payload["payment_id"] == payment_id
    assert voucher_payload["document_id"] == document_id


def test_payment_schema_uuid_fields_are_typed() -> None:
    assert PaymentRead.model_fields["sub_project_id"].annotation is UUID
    assert PaymentRead.model_fields["operator_id"].annotation == UUID | None
    assert PaymentRead.model_fields["payment_date"].annotation is date
    assert PaymentVoucherRead.model_fields["document_id"].annotation is UUID
