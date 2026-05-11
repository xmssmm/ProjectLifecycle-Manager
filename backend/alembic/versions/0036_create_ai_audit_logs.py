"""Create AI audit logs.

Revision ID: 0036_create_ai_audit_logs
Revises: 0035_create_project_taxonomy
Create Date: 2026-05-12 04:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0036_create_ai_audit_logs"
down_revision: str | None = "0035_create_project_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AI_AUDIT_STATUSES = ("succeeded", "failed")


def upgrade() -> None:
    audit_status = postgresql.ENUM(*AI_AUDIT_STATUSES, name="ai_audit_status")
    audit_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("schema_name", sa.String(length=80), nullable=False),
        sa.Column(
            "prompt_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("token_estimate", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*AI_AUDIT_STATUSES, name="ai_audit_status", create_type=False),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_audit_logs_actor_created",
        "ai_audit_logs",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_ai_audit_logs_purpose_created",
        "ai_audit_logs",
        ["purpose", "created_at"],
    )
    op.create_index(
        "ix_ai_audit_logs_status_created",
        "ai_audit_logs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_audit_logs_status_created", table_name="ai_audit_logs")
    op.drop_index("ix_ai_audit_logs_purpose_created", table_name="ai_audit_logs")
    op.drop_index("ix_ai_audit_logs_actor_created", table_name="ai_audit_logs")
    op.drop_table("ai_audit_logs")
    postgresql.ENUM(name="ai_audit_status").drop(op.get_bind(), checkfirst=True)
