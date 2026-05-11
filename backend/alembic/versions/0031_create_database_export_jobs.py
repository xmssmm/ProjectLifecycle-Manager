"""Create database export jobs.

Revision ID: 0031_create_database_export_jobs
Revises: 0030_create_document_search_entries
Create Date: 2026-05-11 20:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0031_create_database_export_jobs"
down_revision: str | None = "0030_create_document_search_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


database_export_job_status = sa.Enum(
    "queued",
    "running",
    "completed",
    "failed",
    name="database_export_job_status",
)


def upgrade() -> None:
    database_export_job_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "database_export_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            database_export_job_status,
            server_default="queued",
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("table_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="ck_database_export_jobs_progress_range",
        ),
        sa.CheckConstraint(
            "table_count >= 0",
            name="ck_database_export_jobs_table_count_non_negative",
        ),
        sa.CheckConstraint(
            "row_count >= 0",
            name="ck_database_export_jobs_row_count_non_negative",
        ),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_database_export_jobs_requested_by_created",
        "database_export_jobs",
        ["requested_by_id", "created_at"],
    )
    op.create_index(
        "ix_database_export_jobs_requested_by_id",
        "database_export_jobs",
        ["requested_by_id"],
    )
    op.create_index("ix_database_export_jobs_status", "database_export_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_database_export_jobs_status", table_name="database_export_jobs")
    op.drop_index(
        "ix_database_export_jobs_requested_by_id",
        table_name="database_export_jobs",
    )
    op.drop_index(
        "ix_database_export_jobs_requested_by_created",
        table_name="database_export_jobs",
    )
    op.drop_table("database_export_jobs")
    database_export_job_status.drop(op.get_bind(), checkfirst=True)
