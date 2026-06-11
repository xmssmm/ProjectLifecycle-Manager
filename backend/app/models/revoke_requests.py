from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.phases import Phase
    from app.models.sub_projects import SubProject
    from app.models.users import User


class RevokeRequestStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RevokeReviewDecision(enum.StrEnum):
    approve = "approve"
    reject = "reject"


class RevokeRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "revoke_requests"
    __table_args__ = (
        Index("ix_revoke_requests_phase_id", "phase_id"),
        Index("ix_revoke_requests_sub_project_id", "sub_project_id"),
        Index("ix_revoke_requests_requester_id", "requester_id"),
        Index("ix_revoke_requests_reviewer_id", "reviewer_id"),
        Index("ix_revoke_requests_status", "status"),
        Index(
            "uq_revoke_requests_pending_phase",
            "phase_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    phase_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requester_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    keep_documents: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    status: Mapped[RevokeRequestStatus] = mapped_column(
        Enum(RevokeRequestStatus, name="revoke_request_status", values_callable=enum_values),
        nullable=False,
        default=RevokeRequestStatus.pending,
        server_default=RevokeRequestStatus.pending.value,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    phase: Mapped[Phase] = relationship()
    sub_project: Mapped[SubProject] = relationship()
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])
