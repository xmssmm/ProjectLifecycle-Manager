from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.users import enum_values

if TYPE_CHECKING:
    from app.models.users import User


class NotificationDeliveryStatus(enum.StrEnum):
    pending = "pending"
    retry_scheduled = "retry_scheduled"
    delivered = "delivered"
    dead_letter = "dead_letter"


class NotificationDelivery(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_notification_deliveries_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_notification_deliveries_max_attempts"),
        Index("ix_notification_deliveries_due", "status", "next_retry_at"),
        Index("ix_notification_deliveries_receiver_created", "receiver_id", "created_at"),
        Index("ix_notification_deliveries_channel", "channel"),
        Index("ix_notification_deliveries_scenario", "scenario"),
    )

    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    receiver_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    dedup_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[NotificationDeliveryStatus] = mapped_column(
        Enum(
            NotificationDeliveryStatus,
            name="notification_delivery_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=NotificationDeliveryStatus.pending,
        server_default=NotificationDeliveryStatus.pending.value,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    receiver: Mapped[User] = relationship()
