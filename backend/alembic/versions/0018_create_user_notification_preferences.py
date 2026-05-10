"""Create user notification preferences table.

Revision ID: 0018_create_user_notification_preferences
Revises: 0017_create_report_jobs
Create Date: 2026-05-10 04:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018_create_user_notification_preferences"
down_revision: str | None = "0017_create_report_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_notification_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "scenario",
            name="uq_notification_preferences_user_scenario",
        ),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "user_notification_preferences",
        ["user_id"],
    )
    op.create_index(
        "ix_notification_preferences_scenario",
        "user_notification_preferences",
        ["scenario"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_preferences_scenario",
        table_name="user_notification_preferences",
    )
    op.drop_index(
        "ix_notification_preferences_user_id",
        table_name="user_notification_preferences",
    )
    op.drop_table("user_notification_preferences")
