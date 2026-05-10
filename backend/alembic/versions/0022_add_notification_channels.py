"""Add notification channel preferences.

Revision ID: 0022_add_notification_channels
Revises: 0021_add_user_sso_policy
Create Date: 2026-05-10 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022_add_notification_channels"
down_revision: str | None = "0021_add_user_sso_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHANNEL_DEFAULT = sa.text(
    """'{"in_app": true, "email": false, "wework": false, "dingtalk": false}'::jsonb""",
)


def upgrade() -> None:
    op.add_column(
        "user_notification_preferences",
        sa.Column(
            "channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=CHANNEL_DEFAULT,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_notification_preferences", "channels")
