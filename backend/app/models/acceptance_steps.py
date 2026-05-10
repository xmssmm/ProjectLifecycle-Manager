from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.phases import Phase
    from app.models.users import User


class AcceptanceStepStatus(enum.StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class AcceptanceStep(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "acceptance_steps"
    __table_args__ = (
        UniqueConstraint("phase_id", "step_no", name="uq_acceptance_steps_phase_step_no"),
        Index("ix_acceptance_steps_phase_id", "phase_id"),
        Index("ix_acceptance_steps_responsible_id", "responsible_id"),
        Index("ix_acceptance_steps_status", "status"),
    )

    phase_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(120), nullable=False)
    responsible_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AcceptanceStepStatus] = mapped_column(
        Enum(
            AcceptanceStepStatus,
            name="acceptance_step_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=AcceptanceStepStatus.not_started,
        server_default=AcceptanceStepStatus.not_started.value,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    phase: Mapped[Phase] = relationship()
    responsible: Mapped[User] = relationship()
