from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.users import User


class ReportType(enum.StrEnum):
    project_list = "project_list"
    payment_journal = "payment_journal"
    dept_summary = "dept_summary"
    monthly_summary = "monthly_summary"


class ReportJobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReportJob(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_jobs"
    __table_args__ = (
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_report_jobs_progress_range"),
        CheckConstraint("row_count >= 0", name="ck_report_jobs_row_count_non_negative"),
        Index("ix_report_jobs_requested_by_created", "requested_by_id", "created_at"),
        Index("ix_report_jobs_status", "status"),
        Index("ix_report_jobs_report_type", "report_type"),
        Index("ix_report_jobs_status_finished_at", "status", "finished_at"),
    )

    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type", values_callable=enum_values),
        nullable=False,
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[ReportJobStatus] = mapped_column(
        Enum(ReportJobStatus, name="report_job_status", values_callable=enum_values),
        nullable=False,
        default=ReportJobStatus.queued,
        server_default=ReportJobStatus.queued.value,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    xlsx_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_by: Mapped[User] = relationship()
