from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.users import User


class PhaseStatus(enum.StrEnum):
    waiting = "waiting"
    in_progress = "in_progress"
    completed = "completed"
    revoked = "revoked"


class ProcurementType(enum.StrEnum):
    inquiry = "inquiry"
    bidding = "bidding"
    single_source = "single_source"


class PhaseDocRequirement(enum.StrEnum):
    required = "required"
    conditional = "conditional"
    optional = "optional"


class Phase(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "phases"
    __table_args__ = (
        UniqueConstraint("sub_project_id", "phase_no", name="uq_phases_sub_project_phase_no"),
        CheckConstraint("phase_no BETWEEN 1 AND 6", name="ck_phases_phase_no_range"),
    )

    sub_project_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[PhaseStatus] = mapped_column(
        Enum(PhaseStatus, name="phase_status", values_callable=enum_values),
        nullable=False,
        default=PhaseStatus.waiting,
        server_default=PhaseStatus.waiting.value,
    )
    enter_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    procurement_type: Mapped[ProcurementType | None] = mapped_column(
        Enum(ProcurementType, name="procurement_type", values_callable=enum_values),
        nullable=True,
    )

    histories: Mapped[list[PhaseHistory]] = relationship(
        back_populates="phase",
        cascade="all, delete-orphan",
    )


class PhaseDocTemplate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "phase_doc_templates"
    __table_args__ = (
        CheckConstraint("phase_no BETWEEN 1 AND 6", name="ck_phase_doc_templates_phase_no_range"),
        Index(
            "uq_phase_doc_templates_base",
            "phase_no",
            "doc_type",
            unique=True,
            postgresql_where=text("procurement_type IS NULL"),
        ),
        Index(
            "uq_phase_doc_templates_procurement",
            "phase_no",
            "doc_type",
            "procurement_type",
            unique=True,
            postgresql_where=text("procurement_type IS NOT NULL"),
        ),
    )

    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement: Mapped[PhaseDocRequirement] = mapped_column(
        Enum(PhaseDocRequirement, name="phase_doc_requirement", values_callable=enum_values),
        nullable=False,
    )
    qty_rule: Mapped[str] = mapped_column(String(32), nullable=False)
    procurement_type: Mapped[ProcurementType | None] = mapped_column(
        Enum(ProcurementType, name="procurement_type", values_callable=enum_values),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")


class PhaseHistory(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "phase_history"

    phase_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[PhaseStatus | None] = mapped_column(
        Enum(PhaseStatus, name="phase_status", values_callable=enum_values),
        nullable=True,
    )
    to_status: Mapped[PhaseStatus] = mapped_column(
        Enum(PhaseStatus, name="phase_status", values_callable=enum_values),
        nullable=False,
    )
    changed_by_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    phase: Mapped[Phase] = relationship(back_populates="histories")
    changed_by: Mapped[User | None] = relationship()
