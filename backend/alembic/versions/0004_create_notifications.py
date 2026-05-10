"""Create notifications table.

Revision ID: 0004_create_notifications
Revises: 0003_create_phase_tables
Create Date: 2026-05-10 19:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_create_notifications"
down_revision: str | None = "0003_create_phase_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("receiver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("dedup_key", sa.String(length=512), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_notifications_dedup_key"),
    )
    op.create_index(
        "ix_notifications_receiver_created",
        "notifications",
        ["receiver_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_receiver_read",
        "notifications",
        ["receiver_id", "read_at"],
    )
    op.create_index("ix_notifications_scenario", "notifications", ["scenario"])
    op.create_index("ix_notifications_source_id", "notifications", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_source_id", table_name="notifications")
    op.drop_index("ix_notifications_scenario", table_name="notifications")
    op.drop_index("ix_notifications_receiver_read", table_name="notifications")
    op.drop_index("ix_notifications_receiver_created", table_name="notifications")
    op.drop_table("notifications")
