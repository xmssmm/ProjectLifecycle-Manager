from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.workflows import WorkflowTemplate


class ProjectType(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_project_types_code"),
        Index("ix_project_types_is_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    workflow_templates: Mapped[list[WorkflowTemplate]] = relationship(back_populates="project_type")
