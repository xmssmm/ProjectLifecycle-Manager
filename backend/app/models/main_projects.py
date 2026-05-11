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
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.departments import Department
    from app.models.sub_projects import SubProject
    from app.models.users import User


class MainProjectStatus(enum.StrEnum):
    pending_review = "pending_review"
    reviewing = "reviewing"
    rejected = "rejected"
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    closed = "closed"


class ProjectReviewDecision(enum.StrEnum):
    approve = "approve"
    reject = "reject"


class MainProject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "main_projects"
    __table_args__ = (
        CheckConstraint("total_budget >= 0", name="ck_main_projects_total_budget_non_negative"),
        CheckConstraint("spent_amount >= 0", name="ck_main_projects_spent_amount_non_negative"),
        Index("ix_main_projects_status", "status"),
        Index("ix_main_projects_closed_at", "closed_at"),
    )

    project_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dept_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[MainProjectStatus] = mapped_column(
        Enum(MainProjectStatus, name="main_project_status", values_callable=enum_values),
        nullable=False,
        default=MainProjectStatus.pending_review,
        server_default=MainProjectStatus.pending_review.value,
    )
    total_budget: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    expected_finish_date: Mapped[date] = mapped_column(Date, nullable=False)
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0"),
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creator_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    department: Mapped[Department] = relationship()
    creator: Mapped[User | None] = relationship()
    reviews: Mapped[list[ProjectReview]] = relationship(
        back_populates="main_project",
        cascade="all, delete-orphan",
    )


class ProjectReview(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_reviews"
    __table_args__ = (
        Index("ix_project_reviews_main_created", "main_project_id", "created_at"),
        Index("ix_project_reviews_sub_created", "sub_project_id", "created_at"),
        Index("ix_project_reviews_reviewer_id", "reviewer_id"),
    )

    main_project_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("main_projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    sub_project_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision: Mapped[ProjectReviewDecision] = mapped_column(
        Enum(ProjectReviewDecision, name="project_review_decision", values_callable=enum_values),
        nullable=False,
    )
    from_status: Mapped[MainProjectStatus] = mapped_column(
        Enum(MainProjectStatus, name="main_project_status", values_callable=enum_values),
        nullable=False,
    )
    to_status: Mapped[MainProjectStatus] = mapped_column(
        Enum(MainProjectStatus, name="main_project_status", values_callable=enum_values),
        nullable=False,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_fields: Mapped[dict[str, object]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    admin_override: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    main_project: Mapped[MainProject | None] = relationship(back_populates="reviews")
    sub_project: Mapped[SubProject | None] = relationship()
    reviewer: Mapped[User | None] = relationship()
