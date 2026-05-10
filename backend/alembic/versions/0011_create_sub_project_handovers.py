"""Create sub project handovers table.

Revision ID: 0011_sub_project_handovers
Revises: 0010_sub_project_members
Create Date: 2026-05-10 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_sub_project_handovers"
down_revision: str | None = "0010_sub_project_members"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sub_project_handovers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "operated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
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
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sub_project_handovers_sub_project_operated",
        "sub_project_handovers",
        ["sub_project_id", "operated_at"],
    )
    op.create_index(
        "ix_sub_project_handovers_from_user_id",
        "sub_project_handovers",
        ["from_user_id"],
    )
    op.create_index(
        "ix_sub_project_handovers_to_user_id",
        "sub_project_handovers",
        ["to_user_id"],
    )
    op.create_index(
        "ix_sub_project_handovers_operator_id",
        "sub_project_handovers",
        ["operator_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sub_project_handovers_operator_id", table_name="sub_project_handovers")
    op.drop_index("ix_sub_project_handovers_to_user_id", table_name="sub_project_handovers")
    op.drop_index("ix_sub_project_handovers_from_user_id", table_name="sub_project_handovers")
    op.drop_index(
        "ix_sub_project_handovers_sub_project_operated",
        table_name="sub_project_handovers",
    )
    op.drop_table("sub_project_handovers")
