from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.sub_projects import SubProject
    from app.models.users import User


class HandoverRequestStatus(enum.StrEnum):
    pending_candidate = "pending_candidate"
    candidate_rejected = "candidate_rejected"
    pending_review = "pending_review"
    review_rejected = "review_rejected"
    approved = "approved"
    forced = "forced"


class HandoverRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "handover_requests"
    __table_args__ = (
        Index("ix_handover_requests_from_user_id", "from_user_id"),
        Index("ix_handover_requests_to_user_id", "to_user_id"),
        Index("ix_handover_requests_status", "status"),
        Index("ix_handover_requests_reviewer_id", "reviewer_id"),
        Index("ix_handover_requests_forced_by_id", "forced_by_id"),
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
    status: Mapped[HandoverRequestStatus] = mapped_column(
        Enum(
            HandoverRequestStatus,
            name="handover_request_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=HandoverRequestStatus.pending_candidate,
        server_default=HandoverRequestStatus.pending_candidate.value,
    )
    candidate_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forced_by_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    forced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])
    forced_by: Mapped[User | None] = relationship(foreign_keys=[forced_by_id])
    projects: Mapped[list[HandoverRequestProject]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )


class HandoverRequestProject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "handover_request_projects"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "sub_project_id",
            name="uq_handover_request_projects_request_sub_project",
        ),
        Index("ix_handover_request_projects_request_id", "request_id"),
        Index("ix_handover_request_projects_sub_project_id", "sub_project_id"),
    )

    request_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("handover_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="RESTRICT"),
        nullable=False,
    )

    request: Mapped[HandoverRequest] = relationship(back_populates="projects")
    sub_project: Mapped[SubProject] = relationship()
