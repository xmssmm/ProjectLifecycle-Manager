"""Create report jobs table.

Revision ID: 0017_create_report_jobs
Revises: 0016_create_revoke_requests
Create Date: 2026-05-11 03:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_create_report_jobs"
down_revision: str | None = "0016_create_revoke_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPORT_TYPES = ("project_list", "payment_journal", "dept_summary", "monthly_summary")
REPORT_JOB_STATUSES = ("queued", "running", "completed", "failed")


def upgrade() -> None:
    report_type = postgresql.ENUM(*REPORT_TYPES, name="report_type")
    report_job_status = postgresql.ENUM(*REPORT_JOB_STATUSES, name="report_job_status")
    report_type.create(op.get_bind(), checkfirst=True)
    report_job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "report_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "report_type",
            postgresql.ENUM(*REPORT_TYPES, name="report_type", create_type=False),
            nullable=False,
        ),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*REPORT_JOB_STATUSES, name="report_job_status", create_type=False),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("xlsx_storage_key", sa.String(length=500), nullable=True),
        sa.Column("pdf_storage_key", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_report_jobs_progress_range"),
        sa.CheckConstraint("row_count >= 0", name="ck_report_jobs_row_count_non_negative"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_jobs_requested_by_id", "report_jobs", ["requested_by_id"])
    op.create_index(
        "ix_report_jobs_requested_by_created",
        "report_jobs",
        ["requested_by_id", "created_at"],
    )
    op.create_index("ix_report_jobs_report_type", "report_jobs", ["report_type"])
    op.create_index("ix_report_jobs_status", "report_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_report_jobs_status", table_name="report_jobs")
    op.drop_index("ix_report_jobs_report_type", table_name="report_jobs")
    op.drop_index("ix_report_jobs_requested_by_created", table_name="report_jobs")
    op.drop_index("ix_report_jobs_requested_by_id", table_name="report_jobs")
    op.drop_table("report_jobs")
    postgresql.ENUM(name="report_job_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="report_type").drop(op.get_bind(), checkfirst=True)
