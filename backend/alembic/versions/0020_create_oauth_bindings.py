"""Create OAuth bindings.

Revision ID: 0020_create_oauth_bindings
Revises: 0019_add_notification_delivery_modes
Create Date: 2026-05-10 06:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020_create_oauth_bindings"
down_revision: str | None = "0019_add_notification_delivery_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_bindings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_id",
            name="uq_oauth_bindings_provider_external",
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_bindings_user_provider"),
    )
    op.create_index("ix_oauth_bindings_email", "oauth_bindings", ["email"])
    op.create_index("ix_oauth_bindings_provider", "oauth_bindings", ["provider"])
    op.create_index("ix_oauth_bindings_user_id", "oauth_bindings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_bindings_user_id", table_name="oauth_bindings")
    op.drop_index("ix_oauth_bindings_provider", table_name="oauth_bindings")
    op.drop_index("ix_oauth_bindings_email", table_name="oauth_bindings")
    op.drop_table("oauth_bindings")
