from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.users import User


class AiAuditStatus(enum.StrEnum):
    succeeded = "succeeded"
    failed = "failed"


class AiAuditLog(UuidPrimaryKeyMixin, Base):
    __tablename__ = "ai_audit_logs"
    __table_args__ = (
        Index("ix_ai_audit_logs_actor_created", "actor_id", "created_at"),
        Index("ix_ai_audit_logs_purpose_created", "purpose", "created_at"),
        Index("ix_ai_audit_logs_status_created", "status", "created_at"),
    )

    actor_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    schema_name: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[AiAuditStatus] = mapped_column(
        Enum(AiAuditStatus, name="ai_audit_status", values_callable=enum_values),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    actor: Mapped[User | None] = relationship()
