from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.main_projects import MainProject
    from app.models.project_types import ProjectType
    from app.models.users import User


class ProjectTemplateScope(enum.StrEnum):
    private = "private"
    department = "department"
    global_ = "global"


class ProjectCategory(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_project_categories_code"),
        Index("ix_project_categories_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class ProjectTag(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_tags"
    __table_args__ = (
        UniqueConstraint("code", name="uq_project_tags_code"),
        Index("ix_project_tags_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class ProjectTemplate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_templates"
    __table_args__ = (
        Index("ix_project_templates_scope", "scope"),
        Index("ix_project_templates_owner", "owner_id"),
        Index("ix_project_templates_owner_dept", "owner_dept_id"),
        Index("ix_project_templates_category", "category_id"),
        Index("ix_project_templates_source_project", "source_project_id"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[ProjectTemplateScope] = mapped_column(
        Enum(ProjectTemplateScope, name="project_template_scope", values_callable=enum_values),
        nullable=False,
        default=ProjectTemplateScope.private,
        server_default=ProjectTemplateScope.private.value,
    )
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_dept_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_project_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("main_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_project_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_type_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    tag_ids: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    field_defaults: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    phase_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    document_requirements_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    default_task_checklist: Mapped[list[dict[str, Any]]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    owner: Mapped[User] = relationship()
    source_project: Mapped[MainProject | None] = relationship()
    category: Mapped[ProjectCategory | None] = relationship()
    project_type: Mapped[ProjectType | None] = relationship()
