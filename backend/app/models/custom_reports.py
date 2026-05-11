from __future__ import annotations

import enum
from datetime import datetime, time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, Time, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.departments import Department
    from app.models.users import User


class CustomReportShareScope(enum.StrEnum):
    private = "private"
    department = "department"
    global_ = "global"


class CustomReportScheduleFrequency(enum.StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class CustomReportRunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class CustomReportDefinition(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "custom_report_definitions"
    __table_args__ = (
        Index("ix_custom_reports_owner_created", "owner_id", "created_at"),
        Index("ix_custom_reports_dataset", "dataset"),
        Index("ix_custom_reports_share_scope", "share_scope"),
        Index("ix_custom_reports_owner_dept", "owner_dept_id"),
        Index("ix_custom_reports_next_run_at", "next_run_at"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_dept_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    query_config: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    chart_type: Mapped[str] = mapped_column(String(32), nullable=False, default="table")
    share_scope: Mapped[CustomReportShareScope] = mapped_column(
        Enum(
            CustomReportShareScope,
            name="custom_report_share_scope",
            values_callable=enum_values,
        ),
        nullable=False,
        default=CustomReportShareScope.private,
        server_default=CustomReportShareScope.private.value,
    )
    schedule_frequency: Mapped[CustomReportScheduleFrequency | None] = mapped_column(
        Enum(
            CustomReportScheduleFrequency,
            name="custom_report_schedule_frequency",
            values_callable=enum_values,
        ),
        nullable=True,
    )
    schedule_time: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    schedule_day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    owner: Mapped[User] = relationship()
    owner_department: Mapped[Department | None] = relationship()
    runs: Mapped[list[CustomReportRun]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class CustomReportRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "custom_report_runs"
    __table_args__ = (
        Index("ix_custom_report_runs_report_created", "report_id", "created_at"),
        Index("ix_custom_report_runs_status", "status"),
        Index("ix_custom_report_runs_triggered_by", "triggered_by_id"),
    )

    report_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("custom_report_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_by_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[CustomReportRunStatus] = mapped_column(
        Enum(CustomReportRunStatus, name="custom_report_run_status", values_callable=enum_values),
        nullable=False,
        default=CustomReportRunStatus.queued,
        server_default=CustomReportRunStatus.queued.value,
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report: Mapped[CustomReportDefinition] = relationship(back_populates="runs")
    triggered_by: Mapped[User | None] = relationship()
