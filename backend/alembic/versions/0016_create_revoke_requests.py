"""Create revoke request table.

Revision ID: 0016_create_revoke_requests
Revises: 0015_create_acceptance_steps
Create Date: 2026-05-11 02:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_create_revoke_requests"
down_revision: str | None = "0015_create_acceptance_steps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVOKE_REQUEST_STATUSES = ("pending", "approved", "rejected")


def upgrade() -> None:
    revoke_request_status = postgresql.ENUM(
        *REVOKE_REQUEST_STATUSES,
        name="revoke_request_status",
    )
    revoke_request_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "revoke_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("phase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *REVOKE_REQUEST_STATUSES,
                name="revoke_request_status",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revoke_requests_phase_id", "revoke_requests", ["phase_id"])
    op.create_index("ix_revoke_requests_requester_id", "revoke_requests", ["requester_id"])
    op.create_index("ix_revoke_requests_reviewer_id", "revoke_requests", ["reviewer_id"])
    op.create_index("ix_revoke_requests_status", "revoke_requests", ["status"])
    op.create_index("ix_revoke_requests_sub_project_id", "revoke_requests", ["sub_project_id"])
    op.create_index(
        "uq_revoke_requests_pending_phase",
        "revoke_requests",
        ["phase_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_revoke_requests_pending_phase", table_name="revoke_requests")
    op.drop_index("ix_revoke_requests_sub_project_id", table_name="revoke_requests")
    op.drop_index("ix_revoke_requests_status", table_name="revoke_requests")
    op.drop_index("ix_revoke_requests_reviewer_id", table_name="revoke_requests")
    op.drop_index("ix_revoke_requests_requester_id", table_name="revoke_requests")
    op.drop_index("ix_revoke_requests_phase_id", table_name="revoke_requests")
    op.drop_table("revoke_requests")
    postgresql.ENUM(name="revoke_request_status").drop(op.get_bind(), checkfirst=True)
