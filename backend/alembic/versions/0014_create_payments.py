"""Create payment tables.

Revision ID: 0014_create_payments
Revises: 0013_create_tasks
Create Date: 2026-05-11 00:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_create_payments"
down_revision: str | None = "0013_create_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYMENT_TYPES = ("normal", "reversal")


def upgrade() -> None:
    payment_type = postgresql.ENUM(*PAYMENT_TYPES, name="payment_type")
    payment_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("payment_no", sa.String(length=64), nullable=False),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "payment_type",
            postgresql.ENUM(*PAYMENT_TYPES, name="payment_type", create_type=False),
            server_default="normal",
            nullable=False,
        ),
        sa.Column("reverses_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(payment_type = 'reversal' AND reverses_payment_id IS NOT NULL) OR "
            "(payment_type = 'normal' AND reverses_payment_id IS NULL)",
            name="ck_payments_reversal_requires_reference",
        ),
        sa.CheckConstraint(
            "reverses_payment_id IS NULL OR reverses_payment_id <> id",
            name="ck_payments_reversal_not_self",
        ),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reverses_payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_no"),
    )
    op.create_index("ix_payments_operator_id", "payments", ["operator_id"])
    op.create_index("ix_payments_payment_no", "payments", ["payment_no"])
    op.create_index("ix_payments_payment_type", "payments", ["payment_type"])
    op.create_index("ix_payments_reverses_payment_id", "payments", ["reverses_payment_id"])
    op.create_index("ix_payments_sub_project_date", "payments", ["sub_project_id", "payment_date"])
    op.create_index("ix_payments_sub_project_id", "payments", ["sub_project_id"])

    op.create_table(
        "payment_vouchers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_payment_vouchers_document_id", "payment_vouchers", ["document_id"])
    op.create_index("ix_payment_vouchers_payment_id", "payment_vouchers", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_vouchers_payment_id", table_name="payment_vouchers")
    op.drop_index("ix_payment_vouchers_document_id", table_name="payment_vouchers")
    op.drop_table("payment_vouchers")
    op.drop_index("ix_payments_sub_project_id", table_name="payments")
    op.drop_index("ix_payments_sub_project_date", table_name="payments")
    op.drop_index("ix_payments_reverses_payment_id", table_name="payments")
    op.drop_index("ix_payments_payment_type", table_name="payments")
    op.drop_index("ix_payments_payment_no", table_name="payments")
    op.drop_index("ix_payments_operator_id", table_name="payments")
    op.drop_table("payments")
    postgresql.ENUM(name="payment_type").drop(op.get_bind(), checkfirst=True)
