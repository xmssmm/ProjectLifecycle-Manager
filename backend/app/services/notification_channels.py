from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class NotificationChannelType(enum.StrEnum):
    in_app = "in_app"
    email = "email"
    wework = "wework"
    dingtalk = "dingtalk"


DEFAULT_NOTIFICATION_CHANNELS: dict[NotificationChannelType, bool] = {
    NotificationChannelType.in_app: True,
    NotificationChannelType.email: False,
    NotificationChannelType.wework: False,
    NotificationChannelType.dingtalk: False,
}


@dataclass(frozen=True)
class NotificationChannelMessage:
    channel: NotificationChannelType
    receiver_id: UUID
    scenario: str
    source_id: str
    payload: dict[str, object]
    dedup_key: str


@dataclass(frozen=True)
class ChannelDeliveryResult:
    channel: NotificationChannelType
    success: bool
    error: str | None = None


class NotificationChannel(Protocol):
    async def send(self, message: NotificationChannelMessage) -> ChannelDeliveryResult:
        ...


def normalize_channel_settings(
    channels: Mapping[NotificationChannelType, bool] | Mapping[str, bool] | None,
    *,
    in_app_default: bool = True,
) -> dict[NotificationChannelType, bool]:
    normalized = dict(DEFAULT_NOTIFICATION_CHANNELS)
    normalized[NotificationChannelType.in_app] = in_app_default
    if channels is None:
        return normalized

    for channel, enabled in channels.items():
        normalized[NotificationChannelType(channel)] = bool(enabled)
    return normalized
