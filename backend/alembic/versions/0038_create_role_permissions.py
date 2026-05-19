"""create role permissions

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "dept_manager",
                "finance_manager",
                "proj_leader",
                "proj_member",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("permission_code", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", "permission_code", name="uq_role_permissions_role_code"),
    )
    op.create_index("ix_role_permissions_role", "role_permissions", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")
