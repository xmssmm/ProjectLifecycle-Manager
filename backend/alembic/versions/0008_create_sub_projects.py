"""Create sub projects table.

Revision ID: 0008_create_sub_projects
Revises: 0007_create_project_reviews
Create Date: 2026-05-10 22:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_create_sub_projects"
down_revision: str | None = "0007_create_project_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUB_PROJECT_STATUSES = (
    "pending_review",
    "reviewing",
    "rejected",
    "not_started",
    "in_progress",
    "completed",
    "closed",
    "terminated",
)


def upgrade() -> None:
    sub_project_status = postgresql.ENUM(*SUB_PROJECT_STATUSES, name="sub_project_status")
    sub_project_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sub_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("project_no", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("main_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("budget", sa.Numeric(15, 2), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(*SUB_PROJECT_STATUSES, name="sub_project_status", create_type=False),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column("plan_end_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("spent_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
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
        sa.CheckConstraint("budget >= 0", name="ck_sub_projects_budget_non_negative"),
        sa.CheckConstraint("spent_amount >= 0", name="ck_sub_projects_spent_amount_non_negative"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dept_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["main_project_id"], ["main_projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_no"),
    )
    op.create_index("ix_sub_projects_creator_id", "sub_projects", ["creator_id"])
    op.create_index("ix_sub_projects_dept_id", "sub_projects", ["dept_id"])
    op.create_index("ix_sub_projects_main_project_id", "sub_projects", ["main_project_id"])
    op.create_index(
        "ix_sub_projects_main_status",
        "sub_projects",
        ["main_project_id", "status"],
    )
    op.create_index("ix_sub_projects_manager_id", "sub_projects", ["manager_id"])
    op.create_index("ix_sub_projects_project_no", "sub_projects", ["project_no"])
    op.create_index("ix_sub_projects_status", "sub_projects", ["status"])

    op.create_table(
        "sub_project_no_counters",
        sa.Column("main_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_sequence", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["main_project_id"], ["main_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("main_project_id"),
    )


def downgrade() -> None:
    op.drop_table("sub_project_no_counters")
    op.drop_index("ix_sub_projects_status", table_name="sub_projects")
    op.drop_index("ix_sub_projects_project_no", table_name="sub_projects")
    op.drop_index("ix_sub_projects_manager_id", table_name="sub_projects")
    op.drop_index("ix_sub_projects_main_status", table_name="sub_projects")
    op.drop_index("ix_sub_projects_main_project_id", table_name="sub_projects")
    op.drop_index("ix_sub_projects_dept_id", table_name="sub_projects")
    op.drop_index("ix_sub_projects_creator_id", table_name="sub_projects")
    op.drop_table("sub_projects")
    postgresql.ENUM(name="sub_project_status").drop(op.get_bind(), checkfirst=True)
