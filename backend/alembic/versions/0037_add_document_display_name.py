"""add document display name

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-13
"""

import sqlalchemy as sa

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )
    op.execute("UPDATE documents SET display_name = file_name WHERE display_name IS NULL")
    op.alter_column("documents", "display_name", nullable=False)


def downgrade() -> None:
    op.drop_column("documents", "display_name")
