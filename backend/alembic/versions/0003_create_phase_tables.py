"""Create phase tables.

Revision ID: 0003_create_phase_tables
Revises: 0002_create_users_departments
Create Date: 2026-05-10 17:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_create_phase_tables"
down_revision: str | None = "0002_create_users_departments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE_STATUSES = ("waiting", "in_progress", "completed", "revoked")
PROCUREMENT_TYPES = ("inquiry", "bidding", "single_source")
PHASE_DOC_REQUIREMENTS = ("required", "conditional", "optional")


def upgrade() -> None:
    phase_status = postgresql.ENUM(*PHASE_STATUSES, name="phase_status")
    procurement_type = postgresql.ENUM(*PROCUREMENT_TYPES, name="procurement_type")
    phase_doc_requirement = postgresql.ENUM(
        *PHASE_DOC_REQUIREMENTS,
        name="phase_doc_requirement",
    )
    phase_status.create(op.get_bind(), checkfirst=True)
    procurement_type.create(op.get_bind(), checkfirst=True)
    phase_doc_requirement.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "phases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_no", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*PHASE_STATUSES, name="phase_status", create_type=False),
            server_default="waiting",
            nullable=False,
        ),
        sa.Column("enter_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "procurement_type",
            postgresql.ENUM(*PROCUREMENT_TYPES, name="procurement_type", create_type=False),
            nullable=True,
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
        sa.CheckConstraint("phase_no BETWEEN 1 AND 6", name="ck_phases_phase_no_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sub_project_id",
            "phase_no",
            name="uq_phases_sub_project_phase_no",
        ),
    )
    op.create_index("ix_phases_sub_project_id", "phases", ["sub_project_id"])

    op.create_table(
        "phase_doc_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("phase_no", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column(
            "requirement",
            postgresql.ENUM(
                *PHASE_DOC_REQUIREMENTS,
                name="phase_doc_requirement",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("qty_rule", sa.String(length=32), nullable=False),
        sa.Column(
            "procurement_type",
            postgresql.ENUM(*PROCUREMENT_TYPES, name="procurement_type", create_type=False),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            "phase_no BETWEEN 1 AND 6",
            name="ck_phase_doc_templates_phase_no_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_phase_doc_templates_base",
        "phase_doc_templates",
        ["phase_no", "doc_type"],
        unique=True,
        postgresql_where=sa.text("procurement_type IS NULL"),
    )
    op.create_index(
        "uq_phase_doc_templates_procurement",
        "phase_doc_templates",
        ["phase_no", "doc_type", "procurement_type"],
        unique=True,
        postgresql_where=sa.text("procurement_type IS NOT NULL"),
    )

    op.create_table(
        "phase_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "from_status",
            postgresql.ENUM(*PHASE_STATUSES, name="phase_status", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(*PHASE_STATUSES, name="phase_status", create_type=False),
            nullable=False,
        ),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_phase_history_changed_by_id", "phase_history", ["changed_by_id"])
    op.create_index("ix_phase_history_phase_id", "phase_history", ["phase_id"])


def downgrade() -> None:
    op.drop_index("ix_phase_history_phase_id", table_name="phase_history")
    op.drop_index("ix_phase_history_changed_by_id", table_name="phase_history")
    op.drop_table("phase_history")
    op.drop_index("uq_phase_doc_templates_procurement", table_name="phase_doc_templates")
    op.drop_index("uq_phase_doc_templates_base", table_name="phase_doc_templates")
    op.drop_table("phase_doc_templates")
    op.drop_index("ix_phases_sub_project_id", table_name="phases")
    op.drop_table("phases")
    postgresql.ENUM(name="phase_doc_requirement").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="procurement_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="phase_status").drop(op.get_bind(), checkfirst=True)
