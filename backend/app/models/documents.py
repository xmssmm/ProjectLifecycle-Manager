from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.phases import Phase
    from app.models.sub_projects import SubProject
    from app.models.users import User


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
        Index(
            "uq_documents_latest_per_group",
            "sub_project_id",
            "phase_id",
            "doc_type",
            unique=True,
            postgresql_where=text("is_latest IS true"),
        ),
    )

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
        nullable=True,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_latest: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    is_deleted: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    uploader_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    sub_project: Mapped[SubProject] = relationship()
    phase: Mapped[Phase] = relationship()
    uploader: Mapped[User] = relationship()
