"""Create workflow template tables.

Revision ID: 0033_create_workflow_templates
Revises: 0032_add_query_performance_indexes
Create Date: 2026-05-11 23:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0033_create_workflow_templates"
down_revision: str | None = "0032_add_query_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKFLOW_TEMPLATE_STATUSES = ("draft", "published", "archived")


def upgrade() -> None:
    workflow_template_status = postgresql.ENUM(
        *WORKFLOW_TEMPLATE_STATUSES,
        name="workflow_template_status",
    )
    workflow_template_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "project_types",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_project_types_code"),
    )
    op.create_index("ix_project_types_is_active", "project_types", ["is_active"])

    op.create_table(
        "workflow_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("project_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                *WORKFLOW_TEMPLATE_STATUSES,
                name="workflow_template_status",
                create_type=False,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["project_type_id"], ["project_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_type_id",
            "name",
            name="uq_workflow_templates_project_type_name",
        ),
    )
    op.create_index(
        "ix_workflow_templates_project_type_id",
        "workflow_templates",
        ["project_type_id"],
    )
    op.create_index("ix_workflow_templates_status", "workflow_templates", ["status"])
    op.create_index("ix_workflow_templates_created_by_id", "workflow_templates", ["created_by_id"])

    op.create_table(
        "workflow_template_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *WORKFLOW_TEMPLATE_STATUSES,
                name="workflow_template_status",
                create_type=False,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "phase_definitions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["template_id"], ["workflow_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "version_no",
            name="uq_workflow_versions_template_version",
        ),
    )
    op.create_index(
        "ix_workflow_template_versions_template_id",
        "workflow_template_versions",
        ["template_id"],
    )
    op.create_index(
        "ix_workflow_template_versions_status",
        "workflow_template_versions",
        ["status"],
    )

    op.add_column(
        "main_projects",
        sa.Column("project_type_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_main_projects_project_type_id_project_types",
        "main_projects",
        "project_types",
        ["project_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_main_projects_project_type_id", "main_projects", ["project_type_id"])

    op.add_column(
        "sub_projects",
        sa.Column("workflow_template_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sub_projects_workflow_template_version_id_versions",
        "sub_projects",
        "workflow_template_versions",
        ["workflow_template_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_sub_projects_workflow_template_version_id",
        "sub_projects",
        ["workflow_template_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sub_projects_workflow_template_version_id", table_name="sub_projects")
    op.drop_constraint(
        "fk_sub_projects_workflow_template_version_id_versions",
        "sub_projects",
        type_="foreignkey",
    )
    op.drop_column("sub_projects", "workflow_template_version_id")

    op.drop_index("ix_main_projects_project_type_id", table_name="main_projects")
    op.drop_constraint(
        "fk_main_projects_project_type_id_project_types",
        "main_projects",
        type_="foreignkey",
    )
    op.drop_column("main_projects", "project_type_id")

    op.drop_index("ix_workflow_template_versions_status", table_name="workflow_template_versions")
    op.drop_index(
        "ix_workflow_template_versions_template_id",
        table_name="workflow_template_versions",
    )
    op.drop_table("workflow_template_versions")

    op.drop_index("ix_workflow_templates_created_by_id", table_name="workflow_templates")
    op.drop_index("ix_workflow_templates_status", table_name="workflow_templates")
    op.drop_index("ix_workflow_templates_project_type_id", table_name="workflow_templates")
    op.drop_table("workflow_templates")

    op.drop_index("ix_project_types_is_active", table_name="project_types")
    op.drop_table("project_types")

    postgresql.ENUM(name="workflow_template_status").drop(op.get_bind(), checkfirst=True)
