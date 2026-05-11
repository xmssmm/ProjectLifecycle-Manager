"""Create project taxonomy and templates.

Revision ID: 0035_create_project_taxonomy
Revises: 0034_create_custom_reports
Create Date: 2026-05-12 02:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0035_create_project_taxonomy"
down_revision: str | None = "0034_create_custom_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_TEMPLATE_SCOPES = ("private", "department", "global")


def upgrade() -> None:
    template_scope = postgresql.ENUM(*PROJECT_TEMPLATE_SCOPES, name="project_template_scope")
    template_scope.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "project_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_project_categories_code"),
    )
    op.create_index("ix_project_categories_active", "project_categories", ["is_active"])

    op.create_table(
        "project_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_project_tags_code"),
    )
    op.create_index("ix_project_tags_active", "project_tags", ["is_active"])

    op.create_table(
        "project_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "scope",
            postgresql.ENUM(
                *PROJECT_TEMPLATE_SCOPES,
                name="project_template_scope",
                create_type=False,
            ),
            server_default="private",
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_dept_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_project_no", sa.String(length=32), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "tag_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "field_defaults",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "phase_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "document_requirements_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "default_task_checklist",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["category_id"], ["project_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_dept_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_type_id"], ["project_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_project_id"], ["main_projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_templates_scope", "project_templates", ["scope"])
    op.create_index("ix_project_templates_owner", "project_templates", ["owner_id"])
    op.create_index("ix_project_templates_owner_dept", "project_templates", ["owner_dept_id"])
    op.create_index("ix_project_templates_category", "project_templates", ["category_id"])
    op.create_index(
        "ix_project_templates_source_project",
        "project_templates",
        ["source_project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_templates_source_project", table_name="project_templates")
    op.drop_index("ix_project_templates_category", table_name="project_templates")
    op.drop_index("ix_project_templates_owner_dept", table_name="project_templates")
    op.drop_index("ix_project_templates_owner", table_name="project_templates")
    op.drop_index("ix_project_templates_scope", table_name="project_templates")
    op.drop_table("project_templates")
    op.drop_index("ix_project_tags_active", table_name="project_tags")
    op.drop_table("project_tags")
    op.drop_index("ix_project_categories_active", table_name="project_categories")
    op.drop_table("project_categories")
    postgresql.ENUM(name="project_template_scope").drop(op.get_bind(), checkfirst=True)
