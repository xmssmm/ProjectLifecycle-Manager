from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.users import User


class ArchiveBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "archive_batches"
    __table_args__ = (
        Index("ix_archive_batches_batch_no", "batch_no", unique=True),
        Index("ix_archive_batches_created_by_id", "created_by_id"),
        Index("ix_archive_batches_finished_at", "finished_at"),
    )

    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    archived_main_project_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_sub_project_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_by: Mapped[User | None] = relationship()


class ArchiveMainProject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "archive_main_projects"
    __table_args__ = (
        Index("ix_archive_main_projects_batch_id", "batch_id"),
        Index("ix_archive_main_projects_original_id", "original_id", unique=True),
        Index("ix_archive_main_projects_project_no", "project_no"),
        Index("ix_archive_main_projects_closed_at", "closed_at"),
    )

    batch_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("archive_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    project_no: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot: Mapped[dict[str, object]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    batch: Mapped[ArchiveBatch] = relationship()


class ArchiveSubProject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "archive_sub_projects"
    __table_args__ = (
        Index("ix_archive_sub_projects_batch_id", "batch_id"),
        Index("ix_archive_sub_projects_original_id", "original_id", unique=True),
        Index("ix_archive_sub_projects_main_project_id", "original_main_project_id"),
        Index("ix_archive_sub_projects_project_no", "project_no"),
        Index("ix_archive_sub_projects_closed_at", "closed_at"),
    )

    batch_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("archive_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    original_main_project_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    project_no: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot: Mapped[dict[str, object]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    batch: Mapped[ArchiveBatch] = relationship()
