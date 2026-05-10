"""Create documents table.

Revision ID: 0012_create_documents
Revises: 0011_sub_project_handovers
Create Date: 2026-05-10 23:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_create_documents"
down_revision: str | None = "0011_sub_project_handovers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "doc_no",
            sa.String(length=64),
            server_default=sa.text("uuid_generate_v4()::text"),
            nullable=False,
        ),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acceptance_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.CheckConstraint("file_size >= 0", name="ck_documents_file_size_non_negative"),
        sa.CheckConstraint("version >= 1", name="ck_documents_version_positive"),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no"),
        sa.UniqueConstraint(
            "sub_project_id",
            "phase_id",
            "doc_type",
            "version",
            name="uq_documents_sub_project_phase_doc_version",
        ),
    )
    op.create_index(
        "ix_documents_acceptance_step_id",
        "documents",
        ["acceptance_step_id"],
    )
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])
    op.create_index("ix_documents_sub_project_phase", "documents", ["sub_project_id", "phase_id"])
    op.create_index("ix_documents_uploader_id", "documents", ["uploader_id"])
    op.create_index(
        "uq_documents_latest_per_group",
        "documents",
        ["sub_project_id", "phase_id", "doc_type"],
        unique=True,
        postgresql_where=sa.text("is_latest IS true"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_latest_per_group", table_name="documents")
    op.drop_index("ix_documents_uploader_id", table_name="documents")
    op.drop_index("ix_documents_sub_project_phase", table_name="documents")
    op.drop_index("ix_documents_doc_type", table_name="documents")
    op.drop_index("ix_documents_acceptance_step_id", table_name="documents")
    op.drop_table("documents")
