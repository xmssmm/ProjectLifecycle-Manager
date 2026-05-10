"""Extend project reviews for sub projects.

Revision ID: 0009_extend_project_reviews
Revises: 0008_create_sub_projects
Create Date: 2026-05-10 22:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_extend_project_reviews"
down_revision: str | None = "0008_create_sub_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_reviews",
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.alter_column("project_reviews", "main_project_id", nullable=True)
    op.create_foreign_key(
        "fk_project_reviews_sub_project_id_sub_projects",
        "project_reviews",
        "sub_projects",
        ["sub_project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_project_reviews_exactly_one_target",
        "project_reviews",
        "(main_project_id IS NOT NULL)::int + (sub_project_id IS NOT NULL)::int = 1",
    )
    op.create_index(
        "ix_project_reviews_sub_created",
        "project_reviews",
        ["sub_project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_reviews_sub_created", table_name="project_reviews")
    op.drop_constraint("ck_project_reviews_exactly_one_target", "project_reviews", type_="check")
    op.drop_constraint(
        "fk_project_reviews_sub_project_id_sub_projects",
        "project_reviews",
        type_="foreignkey",
    )
    op.alter_column("project_reviews", "main_project_id", nullable=False)
    op.drop_column("project_reviews", "sub_project_id")
