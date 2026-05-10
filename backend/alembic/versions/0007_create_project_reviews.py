"""Create project reviews table.

Revision ID: 0007_create_project_reviews
Revises: 0006_create_main_projects
Create Date: 2026-05-10 21:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_create_project_reviews"
down_revision: str | None = "0006_create_main_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_REVIEW_DECISIONS = ("approve", "reject")
MAIN_PROJECT_STATUSES = (
    "pending_review",
    "reviewing",
    "rejected",
    "not_started",
    "in_progress",
    "completed",
    "closed",
)


def upgrade() -> None:
    project_review_decision = postgresql.ENUM(
        *PROJECT_REVIEW_DECISIONS,
        name="project_review_decision",
    )
    project_review_decision.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "project_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("main_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "decision",
            postgresql.ENUM(
                *PROJECT_REVIEW_DECISIONS,
                name="project_review_decision",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            postgresql.ENUM(*MAIN_PROJECT_STATUSES, name="main_project_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(*MAIN_PROJECT_STATUSES, name="main_project_status", create_type=False),
            nullable=False,
        ),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column(
            "modified_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("admin_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["main_project_id"], ["main_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_reviews_main_created",
        "project_reviews",
        ["main_project_id", "created_at"],
    )
    op.create_index("ix_project_reviews_reviewer_id", "project_reviews", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("ix_project_reviews_reviewer_id", table_name="project_reviews")
    op.drop_index("ix_project_reviews_main_created", table_name="project_reviews")
    op.drop_table("project_reviews")
    postgresql.ENUM(name="project_review_decision").drop(op.get_bind(), checkfirst=True)
