"""add revoke request keep documents flag

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "revoke_requests",
        sa.Column("keep_documents", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.alter_column("revoke_requests", "keep_documents", server_default=sa.text("true"))


def downgrade() -> None:
    op.drop_column("revoke_requests", "keep_documents")
