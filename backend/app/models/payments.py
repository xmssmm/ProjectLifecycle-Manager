from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.documents import Document
    from app.models.sub_projects import SubProject
    from app.models.users import User


class PaymentType(enum.StrEnum):
    normal = "normal"
    reversal = "reversal"


class Payment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "(payment_type = 'reversal' AND reverses_payment_id IS NOT NULL) OR "
            "(payment_type = 'normal' AND reverses_payment_id IS NULL)",
            name="ck_payments_reversal_requires_reference",
        ),
        CheckConstraint(
            "reverses_payment_id IS NULL OR reverses_payment_id <> id",
            name="ck_payments_reversal_not_self",
        ),
        Index("ix_payments_sub_project_date", "sub_project_id", "payment_date"),
        Index("ix_payments_payment_type", "payment_type"),
        Index("ix_payments_payment_date", "payment_date"),
    )

    payment_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type", values_callable=enum_values),
        nullable=False,
        default=PaymentType.normal,
        server_default=PaymentType.normal.value,
    )
    reverses_payment_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    operator_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    sub_project: Mapped[SubProject] = relationship()
    operator: Mapped[User | None] = relationship()
    reverses_payment: Mapped[Payment | None] = relationship(remote_side="Payment.id")
    vouchers: Mapped[list[PaymentVoucher]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class PaymentVoucher(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_vouchers"
    __table_args__ = (
        Index("ix_payment_vouchers_payment_id", "payment_id"),
        Index("ix_payment_vouchers_document_id", "document_id"),
    )

    payment_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    payment: Mapped[Payment] = relationship(back_populates="vouchers")
    document: Mapped[Document] = relationship()
