"""Add indexes for critical query performance.

Revision ID: 0032_add_query_performance_indexes
Revises: 0031_create_database_export_jobs
Create Date: 2026-05-11 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032_add_query_performance_indexes"
down_revision: str | None = "0031_create_database_export_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_main_projects_created_at", "main_projects", ["created_at"])
    op.create_index(
        "ix_main_projects_status_created_at",
        "main_projects",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_main_projects_dept_created_at",
        "main_projects",
        ["dept_id", "created_at"],
    )
    op.create_index("ix_sub_projects_created_at", "sub_projects", ["created_at"])
    op.create_index(
        "ix_sub_projects_manager_created_at",
        "sub_projects",
        ["manager_id", "created_at"],
    )
    op.create_index(
        "ix_sub_projects_status_created_at",
        "sub_projects",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_sub_projects_dept_created_at",
        "sub_projects",
        ["dept_id", "created_at"],
    )
    op.create_index(
        "ix_sub_project_members_user_sub_project",
        "sub_project_members",
        ["user_id", "sub_project_id"],
    )
    op.create_index(
        "ix_documents_sub_project_latest_created",
        "documents",
        ["sub_project_id", "created_at"],
        postgresql_where=sa.text("is_latest IS true AND is_deleted IS false"),
    )
    op.create_index(
        "ix_documents_phase_latest_doc_type",
        "documents",
        ["phase_id", "doc_type", "version"],
        postgresql_where=sa.text("is_latest IS true AND is_deleted IS false"),
    )
    op.create_index("ix_tasks_status_plan_end_date", "tasks", ["status", "plan_end_date"])
    op.create_index(
        "ix_task_executors_user_status",
        "task_executors",
        ["user_id", "status"],
    )
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"])
    op.create_index(
        "ix_report_jobs_status_finished_at",
        "report_jobs",
        ["status", "finished_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_jobs_status_finished_at", table_name="report_jobs")
    op.drop_index("ix_payments_payment_date", table_name="payments")
    op.drop_index("ix_task_executors_user_status", table_name="task_executors")
    op.drop_index("ix_tasks_status_plan_end_date", table_name="tasks")
    op.drop_index("ix_documents_phase_latest_doc_type", table_name="documents")
    op.drop_index("ix_documents_sub_project_latest_created", table_name="documents")
    op.drop_index("ix_sub_project_members_user_sub_project", table_name="sub_project_members")
    op.drop_index("ix_sub_projects_dept_created_at", table_name="sub_projects")
    op.drop_index("ix_sub_projects_status_created_at", table_name="sub_projects")
    op.drop_index("ix_sub_projects_manager_created_at", table_name="sub_projects")
    op.drop_index("ix_sub_projects_created_at", table_name="sub_projects")
    op.drop_index("ix_main_projects_dept_created_at", table_name="main_projects")
    op.drop_index("ix_main_projects_status_created_at", table_name="main_projects")
    op.drop_index("ix_main_projects_created_at", table_name="main_projects")
