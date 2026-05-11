"""Create custom report tables.

Revision ID: 0034_create_custom_reports
Revises: 0033_create_workflow_templates
Create Date: 2026-05-12 00:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0034_create_custom_reports"
down_revision: str | None = "0033_create_workflow_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CUSTOM_REPORT_SHARE_SCOPES = ("private", "department", "global")
CUSTOM_REPORT_SCHEDULE_FREQUENCIES = ("daily", "weekly", "monthly")
CUSTOM_REPORT_RUN_STATUSES = ("queued", "running", "completed", "failed")


def upgrade() -> None:
    share_scope = postgresql.ENUM(
        *CUSTOM_REPORT_SHARE_SCOPES,
        name="custom_report_share_scope",
    )
    schedule_frequency = postgresql.ENUM(
        *CUSTOM_REPORT_SCHEDULE_FREQUENCIES,
        name="custom_report_schedule_frequency",
    )
    run_status = postgresql.ENUM(
        *CUSTOM_REPORT_RUN_STATUSES,
        name="custom_report_run_status",
    )
    share_scope.create(op.get_bind(), checkfirst=True)
    schedule_frequency.create(op.get_bind(), checkfirst=True)
    run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "custom_report_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_dept_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column(
            "query_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("chart_type", sa.String(length=32), nullable=False),
        sa.Column(
            "share_scope",
            postgresql.ENUM(
                *CUSTOM_REPORT_SHARE_SCOPES,
                name="custom_report_share_scope",
                create_type=False,
            ),
            server_default="private",
            nullable=False,
        ),
        sa.Column(
            "schedule_frequency",
            postgresql.ENUM(
                *CUSTOM_REPORT_SCHEDULE_FREQUENCIES,
                name="custom_report_schedule_frequency",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("schedule_time", sa.Time(timezone=False), nullable=True),
        sa.Column("schedule_day_of_week", sa.Integer(), nullable=True),
        sa.Column("schedule_day_of_month", sa.Integer(), nullable=True),
        sa.Column("schedule_timezone", sa.String(length=64), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            "schedule_day_of_week IS NULL OR schedule_day_of_week BETWEEN 1 AND 7",
            name="ck_custom_reports_schedule_day_of_week",
        ),
        sa.CheckConstraint(
            "schedule_day_of_month IS NULL OR schedule_day_of_month BETWEEN 1 AND 31",
            name="ck_custom_reports_schedule_day_of_month",
        ),
        sa.ForeignKeyConstraint(["owner_dept_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_custom_reports_owner_created",
        "custom_report_definitions",
        ["owner_id", "created_at"],
    )
    op.create_index("ix_custom_reports_dataset", "custom_report_definitions", ["dataset"])
    op.create_index(
        "ix_custom_reports_share_scope",
        "custom_report_definitions",
        ["share_scope"],
    )
    op.create_index("ix_custom_reports_owner_dept", "custom_report_definitions", ["owner_dept_id"])
    op.create_index("ix_custom_reports_next_run_at", "custom_report_definitions", ["next_run_at"])

    op.create_table(
        "custom_report_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                *CUSTOM_REPORT_RUN_STATUSES,
                name="custom_report_run_status",
                create_type=False,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("file_format", sa.String(length=16), nullable=True),
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
        sa.CheckConstraint("row_count >= 0", name="ck_custom_report_runs_row_count_non_negative"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["custom_report_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["triggered_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_custom_report_runs_report_created",
        "custom_report_runs",
        ["report_id", "created_at"],
    )
    op.create_index("ix_custom_report_runs_status", "custom_report_runs", ["status"])
    op.create_index(
        "ix_custom_report_runs_triggered_by",
        "custom_report_runs",
        ["triggered_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_custom_report_runs_triggered_by", table_name="custom_report_runs")
    op.drop_index("ix_custom_report_runs_status", table_name="custom_report_runs")
    op.drop_index("ix_custom_report_runs_report_created", table_name="custom_report_runs")
    op.drop_table("custom_report_runs")

    op.drop_index("ix_custom_reports_next_run_at", table_name="custom_report_definitions")
    op.drop_index("ix_custom_reports_owner_dept", table_name="custom_report_definitions")
    op.drop_index("ix_custom_reports_share_scope", table_name="custom_report_definitions")
    op.drop_index("ix_custom_reports_dataset", table_name="custom_report_definitions")
    op.drop_index("ix_custom_reports_owner_created", table_name="custom_report_definitions")
    op.drop_table("custom_report_definitions")

    postgresql.ENUM(name="custom_report_run_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="custom_report_schedule_frequency").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="custom_report_share_scope").drop(op.get_bind(), checkfirst=True)
