from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
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


class DatabaseExportJobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class DatabaseExportJob(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_export_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="ck_database_export_jobs_progress_range",
        ),
        CheckConstraint(
            "table_count >= 0",
            name="ck_database_export_jobs_table_count_non_negative",
        ),
        CheckConstraint("row_count >= 0", name="ck_database_export_jobs_row_count_non_negative"),
        Index("ix_database_export_jobs_requested_by_created", "requested_by_id", "created_at"),
        Index("ix_database_export_jobs_status", "status"),
    )

    requested_by_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[DatabaseExportJobStatus] = mapped_column(
        Enum(
            DatabaseExportJobStatus,
            name="database_export_job_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=DatabaseExportJobStatus.queued,
        server_default=DatabaseExportJobStatus.queued.value,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requested_by: Mapped[User] = relationship()
