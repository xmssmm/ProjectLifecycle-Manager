from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

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


class SubProjectMemberRole(enum.StrEnum):
    proj_leader = "proj_leader"
    proj_member = "proj_member"


class SubProject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sub_projects"
    __table_args__ = (
        CheckConstraint("budget >= 0", name="ck_sub_projects_budget_non_negative"),
        CheckConstraint("spent_amount >= 0", name="ck_sub_projects_spent_amount_non_negative"),
        Index("ix_sub_projects_status", "status"),
        Index("ix_sub_projects_main_status", "main_project_id", "status"),
        Index("ix_sub_projects_closed_at", "closed_at"),
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
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    main_project: Mapped[MainProject] = relationship()
    department: Mapped[Department] = relationship()
    manager: Mapped[User] = relationship(foreign_keys=[manager_id])
    creator: Mapped[User | None] = relationship(foreign_keys=[creator_id])


class SubProjectMember(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sub_project_members"
    __table_args__ = (
        UniqueConstraint(
            "sub_project_id",
            "user_id",
            name="uq_sub_project_members_sub_project_user",
        ),
        Index("ix_sub_project_members_sub_project_id", "sub_project_id"),
        Index("ix_sub_project_members_user_id", "user_id"),
    )

    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role_in_project: Mapped[SubProjectMemberRole] = mapped_column(
        Enum(
            SubProjectMemberRole,
            name="sub_project_member_role",
            values_callable=enum_values,
        ),
        nullable=False,
        default=SubProjectMemberRole.proj_member,
        server_default=SubProjectMemberRole.proj_member.value,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    sub_project: Mapped[SubProject] = relationship()
    user: Mapped[User] = relationship()


class SubProjectHandover(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sub_project_handovers"
    __table_args__ = (
        Index("ix_sub_project_handovers_sub_project_operated", "sub_project_id", "operated_at"),
        Index("ix_sub_project_handovers_from_user_id", "from_user_id"),
        Index("ix_sub_project_handovers_to_user_id", "to_user_id"),
        Index("ix_sub_project_handovers_operator_id", "operator_id"),
    )

    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    to_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    operated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    sub_project: Mapped[SubProject] = relationship()
    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])
    operator: Mapped[User] = relationship(foreign_keys=[operator_id])


class SubProjectNoCounter(Base):
    __tablename__ = "sub_project_no_counters"

    main_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("main_projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_sequence: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
