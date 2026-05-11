"""Create archive tables.

Revision ID: 0029_create_archive_tables
Revises: 0028_add_user_timezone
Create Date: 2026-05-11 16:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0029_create_archive_tables"
down_revision: str | None = "0028_add_user_timezone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "main_projects",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sub_projects",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_main_projects_closed_at", "main_projects", ["closed_at"])
    op.create_index("ix_sub_projects_closed_at", "sub_projects", ["closed_at"])

    op.create_table(
        "archive_batches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("batch_no", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="completed", nullable=False),
        sa.Column(
            "archived_main_project_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "archived_sub_project_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_archive_batches_batch_no", "archive_batches", ["batch_no"], unique=True)
    op.create_index("ix_archive_batches_created_by_id", "archive_batches", ["created_by_id"])
    op.create_index("ix_archive_batches_finished_at", "archive_batches", ["finished_at"])

    op.create_table(
        "archive_main_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_no", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["batch_id"], ["archive_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_archive_main_projects_batch_id",
        "archive_main_projects",
        ["batch_id"],
    )
    op.create_index(
        "ix_archive_main_projects_original_id",
        "archive_main_projects",
        ["original_id"],
        unique=True,
    )
    op.create_index(
        "ix_archive_main_projects_project_no",
        "archive_main_projects",
        ["project_no"],
    )
    op.create_index(
        "ix_archive_main_projects_closed_at",
        "archive_main_projects",
        ["closed_at"],
    )

    op.create_table(
        "archive_sub_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_main_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_no", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["batch_id"], ["archive_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_archive_sub_projects_batch_id", "archive_sub_projects", ["batch_id"])
    op.create_index(
        "ix_archive_sub_projects_original_id",
        "archive_sub_projects",
        ["original_id"],
        unique=True,
    )
    op.create_index(
        "ix_archive_sub_projects_main_project_id",
        "archive_sub_projects",
        ["original_main_project_id"],
    )
    op.create_index(
        "ix_archive_sub_projects_project_no",
        "archive_sub_projects",
        ["project_no"],
    )
    op.create_index(
        "ix_archive_sub_projects_closed_at",
        "archive_sub_projects",
        ["closed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_archive_sub_projects_closed_at", table_name="archive_sub_projects")
    op.drop_index("ix_archive_sub_projects_project_no", table_name="archive_sub_projects")
    op.drop_index(
        "ix_archive_sub_projects_main_project_id",
        table_name="archive_sub_projects",
    )
    op.drop_index("ix_archive_sub_projects_original_id", table_name="archive_sub_projects")
    op.drop_index("ix_archive_sub_projects_batch_id", table_name="archive_sub_projects")
    op.drop_table("archive_sub_projects")

    op.drop_index("ix_archive_main_projects_closed_at", table_name="archive_main_projects")
    op.drop_index("ix_archive_main_projects_project_no", table_name="archive_main_projects")
    op.drop_index("ix_archive_main_projects_original_id", table_name="archive_main_projects")
    op.drop_index("ix_archive_main_projects_batch_id", table_name="archive_main_projects")
    op.drop_table("archive_main_projects")

    op.drop_index("ix_archive_batches_finished_at", table_name="archive_batches")
    op.drop_index("ix_archive_batches_created_by_id", table_name="archive_batches")
    op.drop_index("ix_archive_batches_batch_no", table_name="archive_batches")
    op.drop_table("archive_batches")

    op.drop_index("ix_sub_projects_closed_at", table_name="sub_projects")
    op.drop_index("ix_main_projects_closed_at", table_name="main_projects")
    op.drop_column("sub_projects", "closed_at")
    op.drop_column("main_projects", "closed_at")
