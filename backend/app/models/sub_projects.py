from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.departments import Department
    from app.models.main_projects import MainProject
    from app.models.users import User


class SubProjectStatus(enum.StrEnum):
    pending_review = "pending_review"
    reviewing = "reviewing"
    rejected = "rejected"
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    closed = "closed"
    terminated = "terminated"


class SubProject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sub_projects"
    __table_args__ = (
        CheckConstraint("budget >= 0", name="ck_sub_projects_budget_non_negative"),
        CheckConstraint("spent_amount >= 0", name="ck_sub_projects_spent_amount_non_negative"),
        Index("ix_sub_projects_status", "status"),
        Index("ix_sub_projects_main_status", "main_project_id", "status"),
    )

    project_no: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    main_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("main_projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dept_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    budget: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    manager_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[SubProjectStatus] = mapped_column(
        Enum(SubProjectStatus, name="sub_project_status", values_callable=enum_values),
        nullable=False,
        default=SubProjectStatus.pending_review,
        server_default=SubProjectStatus.pending_review.value,
    )
    plan_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    main_project: Mapped[MainProject] = relationship()
    department: Mapped[Department] = relationship()
    manager: Mapped[User] = relationship(foreign_keys=[manager_id])
    creator: Mapped[User | None] = relationship(foreign_keys=[creator_id])


class SubProjectNoCounter(Base):
    __tablename__ = "sub_project_no_counters"

    main_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("main_projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_sequence: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
