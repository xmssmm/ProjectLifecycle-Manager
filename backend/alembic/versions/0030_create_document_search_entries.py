"""Create document search entries.

Revision ID: 0030_create_document_search_entries
Revises: 0029_create_archive_tables
Create Date: 2026-05-11 19:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0030_create_document_search_entries"
down_revision: str | None = "0029_create_archive_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


document_search_status = sa.Enum(
    "indexed",
    "failed",
    "skipped",
    name="document_search_status",
)


def upgrade() -> None:
    document_search_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "document_search_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column("content_text", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "status",
            document_search_status,
            server_default="indexed",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_search_entries_document_id",
        "document_search_entries",
        ["document_id"],
        unique=True,
    )
    op.create_index(
        "ix_document_search_entries_sub_project_id",
        "document_search_entries",
        ["sub_project_id"],
    )
    op.create_index(
        "ix_document_search_entries_phase_id",
        "document_search_entries",
        ["phase_id"],
    )
    op.create_index(
        "ix_document_search_entries_status",
        "document_search_entries",
        ["status"],
    )
    op.create_index(
        "ix_document_search_entries_vector",
        "document_search_entries",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_document_search_entries_vector", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_status", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_phase_id", table_name="document_search_entries")
    op.drop_index(
        "ix_document_search_entries_sub_project_id",
        table_name="document_search_entries",
    )
    op.drop_index("ix_document_search_entries_document_id", table_name="document_search_entries")
    op.drop_table("document_search_entries")
    document_search_status.drop(op.get_bind(), checkfirst=True)
