"""Add user timezone.

Revision ID: 0028_add_user_timezone
Revises: 0027_create_webhooks
Create Date: 2026-05-11 13:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_add_user_timezone"
down_revision: str | None = "0027_create_webhooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TIMEZONE = "Asia/Shanghai"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=DEFAULT_TIMEZONE,
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
