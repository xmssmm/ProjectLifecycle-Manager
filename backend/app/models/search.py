from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.documents import Document
    from app.models.phases import Phase
    from app.models.sub_projects import SubProject


class DocumentSearchStatus(enum.StrEnum):
    indexed = "indexed"
    failed = "failed"
    skipped = "skipped"


class DocumentSearchEntry(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_search_entries"
    __table_args__ = (
        Index("ix_document_search_entries_document_id", "document_id", unique=True),
        Index("ix_document_search_entries_sub_project_id", "sub_project_id"),
        Index("ix_document_search_entries_phase_id", "phase_id"),
        Index("ix_document_search_entries_status", "status"),
        Index(
            "ix_document_search_entries_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    sub_project_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    phase_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[DocumentSearchStatus] = mapped_column(
        Enum(DocumentSearchStatus, name="document_search_status", values_callable=enum_values),
        nullable=False,
        default=DocumentSearchStatus.indexed,
        server_default=DocumentSearchStatus.indexed.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    search_vector: Mapped[Any | None] = mapped_column(postgresql.TSVECTOR, nullable=True)

    document: Mapped[Document] = relationship()
    sub_project: Mapped[SubProject] = relationship()
    phase: Mapped[Phase] = relationship()
