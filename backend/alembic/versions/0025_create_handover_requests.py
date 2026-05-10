"""Create self-service handover requests.

Revision ID: 0025_create_handover_requests
Revises: 0024_add_document_scan_status
Create Date: 2026-05-10 08:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0025_create_handover_requests"
down_revision: str | None = "0024_add_document_scan_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HANDOVER_REQUEST_STATUSES = (
    "pending_candidate",
    "candidate_rejected",
    "pending_review",
    "review_rejected",
    "approved",
    "forced",
)


def upgrade() -> None:
    request_status = postgresql.ENUM(
        *HANDOVER_REQUEST_STATUSES,
        name="handover_request_status",
    )
    request_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "handover_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *HANDOVER_REQUEST_STATUSES,
                name="handover_request_status",
                create_type=False,
            ),
            server_default="pending_candidate",
            nullable=False,
        ),
        sa.Column("candidate_comment", sa.Text(), nullable=True),
        sa.Column("candidate_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("forced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["forced_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_handover_requests_forced_by_id", "handover_requests", ["forced_by_id"])
    op.create_index("ix_handover_requests_from_user_id", "handover_requests", ["from_user_id"])
    op.create_index("ix_handover_requests_reviewer_id", "handover_requests", ["reviewer_id"])
    op.create_index("ix_handover_requests_status", "handover_requests", ["status"])
    op.create_index("ix_handover_requests_to_user_id", "handover_requests", ["to_user_id"])

    op.create_table(
        "handover_request_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["request_id"], ["handover_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            "sub_project_id",
            name="uq_handover_request_projects_request_sub_project",
        ),
    )
    op.create_index(
        "ix_handover_request_projects_request_id",
        "handover_request_projects",
        ["request_id"],
    )
    op.create_index(
        "ix_handover_request_projects_sub_project_id",
        "handover_request_projects",
        ["sub_project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_handover_request_projects_sub_project_id",
        table_name="handover_request_projects",
    )
    op.drop_index(
        "ix_handover_request_projects_request_id",
        table_name="handover_request_projects",
    )
    op.drop_table("handover_request_projects")
    op.drop_index("ix_handover_requests_to_user_id", table_name="handover_requests")
    op.drop_index("ix_handover_requests_status", table_name="handover_requests")
    op.drop_index("ix_handover_requests_reviewer_id", table_name="handover_requests")
    op.drop_index("ix_handover_requests_from_user_id", table_name="handover_requests")
    op.drop_index("ix_handover_requests_forced_by_id", table_name="handover_requests")
    op.drop_table("handover_requests")
    postgresql.ENUM(name="handover_request_status").drop(op.get_bind(), checkfirst=True)
