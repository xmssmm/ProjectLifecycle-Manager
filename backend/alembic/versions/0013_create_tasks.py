"""Create task tables.

Revision ID: 0013_create_tasks
Revises: 0012_create_documents
Create Date: 2026-05-10 23:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_create_tasks"
down_revision: str | None = "0012_create_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TASK_STATUSES = ("not_started", "in_progress", "overdue", "completed")


def upgrade() -> None:
    task_status = postgresql.ENUM(*TASK_STATUSES, name="task_status")
    task_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("task_no", sa.String(length=64), nullable=False),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("plan_end_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*TASK_STATUSES, name="task_status", create_type=False),
            server_default="not_started",
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
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_no"),
    )
    op.create_index("ix_tasks_phase_id", "tasks", ["phase_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_sub_project_id", "tasks", ["sub_project_id"])
    op.create_index("ix_tasks_sub_project_phase", "tasks", ["sub_project_id", "phase_id"])
    op.create_index("ix_tasks_task_no", "tasks", ["task_no"])

    op.create_table(
        "task_executors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_end_date", sa.Date(), nullable=False),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(*TASK_STATUSES, name="task_status", create_type=False),
            server_default="not_started",
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
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_executors_task_user"),
    )
    op.create_index("ix_task_executors_status", "task_executors", ["status"])
    op.create_index("ix_task_executors_task_id", "task_executors", ["task_id"])
    op.create_index("ix_task_executors_user_id", "task_executors", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_task_executors_user_id", table_name="task_executors")
    op.drop_index("ix_task_executors_task_id", table_name="task_executors")
    op.drop_index("ix_task_executors_status", table_name="task_executors")
    op.drop_table("task_executors")
    op.drop_index("ix_tasks_task_no", table_name="tasks")
    op.drop_index("ix_tasks_sub_project_phase", table_name="tasks")
    op.drop_index("ix_tasks_sub_project_id", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_phase_id", table_name="tasks")
    op.drop_table("tasks")
    postgresql.ENUM(name="task_status").drop(op.get_bind(), checkfirst=True)
