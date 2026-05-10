"""Add notification delivery modes.

Revision ID: 0019_add_notification_delivery_modes
Revises: 0018_create_user_notification_preferences
Create Date: 2026-05-10 05:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_add_notification_delivery_modes"
down_revision: str | None = "0018_create_user_notification_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column(
            "delivery_mode",
            sa.String(length=32),
            server_default="real_time",
            nullable=False,
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("digest_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notifications_digest_pending",
        "notifications",
        ["delivery_mode", "digest_sent_at", "created_at"],
    )
    op.add_column(
        "user_notification_preferences",
        sa.Column(
            "delivery_mode",
            sa.String(length=32),
            server_default="real_time",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_notification_preferences", "delivery_mode")
    op.drop_index("ix_notifications_digest_pending", table_name="notifications")
    op.drop_column("notifications", "digest_sent_at")
    op.drop_column("notifications", "delivery_mode")
