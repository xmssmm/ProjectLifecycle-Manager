"""Create main projects table.

Revision ID: 0006_create_main_projects
Revises: 0005_create_audit_logs
Create Date: 2026-05-10 20:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_create_main_projects"
down_revision: str | None = "0005_create_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    main_project_status = postgresql.ENUM(*MAIN_PROJECT_STATUSES, name="main_project_status")
    main_project_status.create(op.get_bind(), checkfirst=True)
    op.execute("CREATE SEQUENCE IF NOT EXISTS main_project_no_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "main_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("project_no", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("dept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*MAIN_PROJECT_STATUSES, name="main_project_status", create_type=False),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column("total_budget", sa.Numeric(15, 2), nullable=False),
        sa.Column("expected_finish_date", sa.Date(), nullable=False),
        sa.Column("spent_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint(
            "total_budget >= 0",
            name="ck_main_projects_total_budget_non_negative",
        ),
        sa.CheckConstraint(
            "spent_amount >= 0",
            name="ck_main_projects_spent_amount_non_negative",
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dept_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_no"),
    )
    op.create_index("ix_main_projects_creator_id", "main_projects", ["creator_id"])
    op.create_index("ix_main_projects_dept_id", "main_projects", ["dept_id"])
    op.create_index("ix_main_projects_project_no", "main_projects", ["project_no"])
    op.create_index("ix_main_projects_status", "main_projects", ["status"])


def downgrade() -> None:
    op.drop_index("ix_main_projects_status", table_name="main_projects")
    op.drop_index("ix_main_projects_project_no", table_name="main_projects")
    op.drop_index("ix_main_projects_dept_id", table_name="main_projects")
    op.drop_index("ix_main_projects_creator_id", table_name="main_projects")
    op.drop_table("main_projects")
    op.execute("DROP SEQUENCE IF EXISTS main_project_no_seq")
    postgresql.ENUM(name="main_project_status").drop(op.get_bind(), checkfirst=True)
