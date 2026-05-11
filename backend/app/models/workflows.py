from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.exceptions import ResourceConflictError
from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.project_types import ProjectType
    from app.models.users import User


class WorkflowTemplateStatus(enum.StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class WorkflowTemplate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint("project_type_id", "name", name="uq_workflow_templates_project_type_name"),
        Index("ix_workflow_templates_project_type_id", "project_type_id"),
        Index("ix_workflow_templates_status", "status"),
    )

    project_type_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WorkflowTemplateStatus] = mapped_column(
        Enum(WorkflowTemplateStatus, name="workflow_template_status", values_callable=enum_values),
        nullable=False,
        default=WorkflowTemplateStatus.draft,
        server_default=WorkflowTemplateStatus.draft.value,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    project_type: Mapped[ProjectType] = relationship(back_populates="workflow_templates")
    created_by: Mapped[User | None] = relationship()
    versions: Mapped[list[WorkflowTemplateVersion]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
    )


class WorkflowTemplateVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_no", name="uq_workflow_versions_template_version"),
        Index("ix_workflow_template_versions_template_id", "template_id"),
        Index("ix_workflow_template_versions_status", "status"),
    )

    template_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workflow_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[WorkflowTemplateStatus] = mapped_column(
        Enum(WorkflowTemplateStatus, name="workflow_template_status", values_callable=enum_values),
        nullable=False,
        default=WorkflowTemplateStatus.draft,
        server_default=WorkflowTemplateStatus.draft.value,
    )
    phase_definitions: Mapped[list[dict[str, object]]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped[WorkflowTemplate] = relationship(back_populates="versions")

    def replace_phase_definitions(self, phase_definitions: list[dict[str, object]]) -> None:
        if self.status == WorkflowTemplateStatus.published:
            raise ResourceConflictError("已发布的工作流模板版本不可修改")
        self.phase_definitions = phase_definitions
