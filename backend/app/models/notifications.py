from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.users import User


class Notification(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_notifications_dedup_key"),
        Index("ix_notifications_receiver_created", "receiver_id", "created_at"),
        Index("ix_notifications_receiver_read", "receiver_id", "read_at"),
        Index("ix_notifications_scenario", "scenario"),
        Index("ix_notifications_source_id", "source_id"),
        Index("ix_notifications_digest_pending", "delivery_mode", "digest_sent_at", "created_at"),
    )

    receiver_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    dedup_key: Mapped[str] = mapped_column(String(512), nullable=False)
    delivery_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="real_time",
        server_default="real_time",
    )
    digest_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    receiver: Mapped[User] = relationship()


class NotificationPreference(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "scenario", name="uq_notification_preferences_user_scenario"),
        Index("ix_notification_preferences_user_id", "user_id"),
        Index("ix_notification_preferences_scenario", "scenario"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="real_time",
        server_default="real_time",
    )
    channels: Mapped[dict[str, bool]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text(
            """'{"in_app": true, "email": false, "wework": false, "dingtalk": false}'::jsonb""",
        ),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    user: Mapped[User] = relationship()
