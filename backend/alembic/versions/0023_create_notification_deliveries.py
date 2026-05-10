"""Create notification deliveries table.

Revision ID: 0023_create_notification_deliveries
Revises: 0022_add_notification_channels
Create Date: 2026-05-10 07:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0023_create_notification_deliveries"
down_revision: str | None = "0022_add_notification_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DELIVERY_STATUSES = ("pending", "retry_scheduled", "delivered", "dead_letter")


def upgrade() -> None:
    delivery_status = postgresql.ENUM(*DELIVERY_STATUSES, name="notification_delivery_status")
    delivery_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notification_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("scenario", sa.String(length=64), nullable=False),
        sa.Column("receiver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("dedup_key", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *DELIVERY_STATUSES,
                name="notification_delivery_status",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
            "attempt_count >= 0",
            name="ck_notification_deliveries_attempt_count",
        ),
        sa.CheckConstraint("max_attempts > 0", name="ck_notification_deliveries_max_attempts"),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_deliveries_channel",
        "notification_deliveries",
        ["channel"],
    )
    op.create_index(
        "ix_notification_deliveries_due",
        "notification_deliveries",
        ["status", "next_retry_at"],
    )
    op.create_index(
        "ix_notification_deliveries_receiver_created",
        "notification_deliveries",
        ["receiver_id", "created_at"],
    )
    op.create_index(
        "ix_notification_deliveries_scenario",
        "notification_deliveries",
        ["scenario"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_scenario", table_name="notification_deliveries")
    op.drop_index(
        "ix_notification_deliveries_receiver_created",
        table_name="notification_deliveries",
    )
    op.drop_index("ix_notification_deliveries_due", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_channel", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    postgresql.ENUM(name="notification_delivery_status").drop(op.get_bind(), checkfirst=True)
