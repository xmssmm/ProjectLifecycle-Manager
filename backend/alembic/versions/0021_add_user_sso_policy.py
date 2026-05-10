"""Add user SSO policy.

Revision ID: 0021_add_user_sso_policy
Revises: 0020_create_oauth_bindings
Create Date: 2026-05-10 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_add_user_sso_policy"
down_revision: str | None = "0020_create_oauth_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "sso_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "sso_required")
