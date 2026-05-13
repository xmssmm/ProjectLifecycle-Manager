from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.phases import Phase
    from app.models.sub_projects import SubProject
    from app.models.users import User


class DocumentScanStatus(enum.StrEnum):
    pending = "pending"
    clean = "clean"
    infected = "infected"
    failed = "failed"


class Document(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "sub_project_id",
            "phase_id",
            "doc_type",
            "version",
            name="uq_documents_sub_project_phase_doc_version",
        ),
        CheckConstraint("file_size >= 0", name="ck_documents_file_size_non_negative"),
        CheckConstraint("version >= 1", name="ck_documents_version_positive"),
        Index("ix_documents_sub_project_phase", "sub_project_id", "phase_id"),
        Index("ix_documents_doc_type", "doc_type"),
        Index("ix_documents_scan_status", "scan_status"),
        Index(
            "ix_documents_sub_project_latest_created",
            "sub_project_id",
            "created_at",
            postgresql_where=text("is_latest IS true AND is_deleted IS false"),
        ),
        Index(
            "ix_documents_phase_latest_doc_type",
            "phase_id",
            "doc_type",
            "version",
            postgresql_where=text("is_latest IS true AND is_deleted IS false"),
        ),
        Index(
            "uq_documents_latest_per_group",
            "sub_project_id",
            "phase_id",
            "doc_type",
            unique=True,
            postgresql_where=text("is_latest IS true"),
        ),
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("scan_status", DocumentScanStatus.clean)
        kwargs.setdefault("scan_result", None)
        kwargs.setdefault("scanned_at", None)
        if "display_name" not in kwargs and "file_name" in kwargs:
            kwargs["display_name"] = kwargs["file_name"]
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise TypeError(f"{key!r} is an invalid keyword argument for Document")
            setattr(self, key, value)

    doc_no: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        default=lambda: str(uuid4()),
        server_default=text("uuid_generate_v4()::text"),
    )
    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    phase_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    acceptance_step_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("acceptance_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_latest: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    is_deleted: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    scan_status: Mapped[DocumentScanStatus] = mapped_column(
        Enum(DocumentScanStatus, name="document_scan_status", values_callable=enum_values),
        nullable=False,
        default=DocumentScanStatus.pending,
        server_default=DocumentScanStatus.clean.value,
    )
    scan_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploader_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    sub_project: Mapped[SubProject] = relationship()
    phase: Mapped[Phase] = relationship()
    uploader: Mapped[User] = relationship()
