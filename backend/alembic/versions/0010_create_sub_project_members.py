"""Create sub project members table.

Revision ID: 0010_sub_project_members
Revises: 0009_extend_project_reviews
Create Date: 2026-05-10 23:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_sub_project_members"
down_revision: str | None = "0009_extend_project_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUB_PROJECT_MEMBER_ROLES = ("proj_leader", "proj_member")


def upgrade() -> None:
    member_role = postgresql.ENUM(*SUB_PROJECT_MEMBER_ROLES, name="sub_project_member_role")
    member_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sub_project_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("sub_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role_in_project",
            postgresql.ENUM(
                *SUB_PROJECT_MEMBER_ROLES,
                name="sub_project_member_role",
                create_type=False,
            ),
            server_default="proj_member",
            nullable=False,
        ),
        sa.Column(
            "joined_at",
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
        sa.ForeignKeyConstraint(["sub_project_id"], ["sub_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sub_project_id",
            "user_id",
            name="uq_sub_project_members_sub_project_user",
        ),
    )
    op.create_index(
        "ix_sub_project_members_sub_project_id",
        "sub_project_members",
        ["sub_project_id"],
    )
    op.create_index("ix_sub_project_members_user_id", "sub_project_members", ["user_id"])

    op.execute(
        """
        INSERT INTO sub_project_members (
            id,
            sub_project_id,
            user_id,
            role_in_project,
            joined_at,
            created_at,
            updated_at
        )
        SELECT uuid_generate_v4(), id, manager_id, 'proj_leader', now(), now(), now()
        FROM sub_projects
        ON CONFLICT (sub_project_id, user_id) DO NOTHING
        """,
    )


def downgrade() -> None:
    op.drop_index("ix_sub_project_members_user_id", table_name="sub_project_members")
    op.drop_index("ix_sub_project_members_sub_project_id", table_name="sub_project_members")
    op.drop_table("sub_project_members")
    postgresql.ENUM(name="sub_project_member_role").drop(op.get_bind(), checkfirst=True)
