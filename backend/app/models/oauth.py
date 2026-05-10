from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.users import User


class OAuthBinding(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_bindings"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_oauth_bindings_provider_external"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_bindings_user_provider"),
        Index("ix_oauth_bindings_user_id", "user_id"),
        Index("ix_oauth_bindings_provider", "provider"),
        Index("ix_oauth_bindings_email", "email"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
