from __future__ import annotations

import enum
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, ValidationFailedError
from app.models.notifications import Notification, NotificationPreference
from app.models.users import User
from app.services.notification_channels import (
    NotificationChannel,
    NotificationChannelMessage,
    NotificationChannelType,
    normalize_channel_settings,
)
from app.services.notification_deliveries import NotificationDeliveryService

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
DAILY_DIGEST_SCENARIO = "daily_digest"


def current_business_date() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


def current_utc_datetime() -> datetime:
    return datetime.now(UTC)


class NotificationDeliveryMode(enum.StrEnum):
    real_time = "real_time"
    daily_digest = "daily_digest"


@dataclass(frozen=True)
class NotificationPage:
    items: list[Notification]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class NotificationScenarioDefinition:
    scenario: str
    label: str
    description: str
    direct_related: bool


@dataclass(frozen=True)
class NotificationPreferenceState:
    scenario: str
    label: str
    description: str
    direct_related: bool
    enabled: bool
    delivery_mode: NotificationDeliveryMode
    channels: dict[NotificationChannelType, bool]


@dataclass(frozen=True)
class StoredNotificationPreference:
    enabled: bool
    delivery_mode: NotificationDeliveryMode
    channels: (
        Mapping[NotificationChannelType, bool]
        | Mapping[str, bool]
        | None
    ) = None

    def channel_enabled(self, channel: NotificationChannelType) -> bool:
        channels = self.normalized_channels()
        return channels[channel]

    def normalized_channels(self) -> dict[NotificationChannelType, bool]:
        return normalize_channel_settings(
            self.channels,
            in_app_default=self.enabled,
        )


@dataclass(frozen=True)
class NotificationDigestResult:
    business_date: date
    source_notification_count: int
    digest_notification_count: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "business_date": self.business_date.isoformat(),
            "source_notification_count": self.source_notification_count,
            "digest_notification_count": self.digest_notification_count,
        }


NOTIFICATION_SCENARIOS: tuple[NotificationScenarioDefinition, ...] = (
    NotificationScenarioDefinition(
        scenario="project_pending_review",
        label="项目待审核",
        description="主项目或子项目提交后等待审核",
        direct_related=False,
    ),
    NotificationScenarioDefinition(
        scenario="project_review_result",
        label="审核结果",
        description="提交的项目审核通过或驳回",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="task_assigned",
        label="任务分配",
        description="被分配为任务执行人",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="task_due_today",
        label="任务今日到期",
        description="负责的任务计划今日完成",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="task_overdue",
        label="任务逾期",
        description="负责的任务已经逾期",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="task_overdue_escalation",
        label="逾期升级",
        description="管理人员收到任务逾期升级提醒",
        direct_related=False,
    ),
    NotificationScenarioDefinition(
        scenario="payment_created",
        label="付款登记",
        description="关联项目新增付款记录",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="over_budget_warning",
        label="预算预警",
        description="付款后项目预算使用触发预警",
        direct_related=False,
    ),
    NotificationScenarioDefinition(
        scenario="revoke_request_pending",
        label="撤回待审核",
        description="项目环节撤回申请等待审核",
        direct_related=False,
    ),
    NotificationScenarioDefinition(
        scenario="revoke_result",
        label="撤回结果",
        description="提交的撤回申请审核完成",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="phase_promoted",
        label="环节推进",
        description="关联项目推进到新环节",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="handover_completed",
        label="负责人转交",
        description="子项目负责人转交完成",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="handover_request_candidate",
        label="转交候选确认",
        description="项目负责人自助转交等待候选人确认",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="handover_request_pending_review",
        label="转交待审核",
        description="候选人已确认，等待部门负责人审核",
        direct_related=False,
    ),
    NotificationScenarioDefinition(
        scenario="handover_request_rejected",
        label="转交被拒绝",
        description="项目负责人自助转交被候选人或审核人拒绝",
        direct_related=True,
    ),
    NotificationScenarioDefinition(
        scenario="document_infected",
        label="文档隔离告警",
        description="上传文档被病毒扫描标记为风险文件",
        direct_related=False,
    ),
)

NOTIFICATION_SCENARIO_BY_CODE = {
    definition.scenario: definition for definition in NOTIFICATION_SCENARIOS
}


class NotificationRepository(Protocol):
    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        ...

    async def disabled_receivers_for_scenario(
        self,
        *,
        scenario: str,
        receiver_ids: Sequence[UUID],
    ) -> set[UUID]:
        ...

    async def preferences_for_scenario(
        self,
        *,
        scenario: str,
        receiver_ids: Sequence[UUID],
    ) -> dict[UUID, StoredNotificationPreference]:
        ...

    async def list_preferences(self, user_id: UUID) -> dict[str, StoredNotificationPreference]:
        ...

    async def upsert_preferences(
        self,
        *,
        user_id: UUID,
        preferences: Mapping[str, StoredNotificationPreference],
    ) -> None:
        ...

    async def list_pending_digest_notifications(self, business_date: date) -> list[Notification]:
        ...

    def mark_digest_notifications_sent(
        self,
        notifications: Sequence[Notification],
        *,
        sent_at: datetime,
    ) -> None:
        ...

    async def list_notifications(
        self,
        *,
        receiver_id: UUID,
        unread: bool | None,
        page: int,
        page_size: int,
    ) -> NotificationPage:
        ...

    async def get_notification(self, notification_id: UUID) -> Notification | None:
        ...

    async def list_unread_for_update(self, receiver_id: UUID) -> list[Notification]:
        ...

    async def count_unread(self, receiver_id: UUID) -> int:
        ...

    def add_many(self, notifications: Sequence[Notification]) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        ...

    async def refresh(self, notification: Notification) -> None:
        ...


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        if not dedup_keys:
            return set()

        result = await self._session.scalars(
            select(Notification.dedup_key).where(Notification.dedup_key.in_(dedup_keys)),
        )
        return set(result.all())

    async def disabled_receivers_for_scenario(
        self,
        *,
        scenario: str,
        receiver_ids: Sequence[UUID],
    ) -> set[UUID]:
        if not receiver_ids:
            return set()

        result = await self._session.scalars(
            select(NotificationPreference.user_id).where(
                NotificationPreference.user_id.in_(receiver_ids),
                NotificationPreference.scenario == scenario,
                NotificationPreference.enabled.is_(False),
            ),
        )
        return set(result.all())

    async def preferences_for_scenario(
        self,
        *,
        scenario: str,
        receiver_ids: Sequence[UUID],
    ) -> dict[UUID, StoredNotificationPreference]:
        if not receiver_ids:
            return {}

        result = await self._session.scalars(
            select(NotificationPreference).where(
                NotificationPreference.user_id.in_(receiver_ids),
                NotificationPreference.scenario == scenario,
            ),
        )
        return {
            preference.user_id: StoredNotificationPreference(
                enabled=preference.enabled,
                delivery_mode=NotificationDeliveryMode(preference.delivery_mode),
                channels=self._preference_channels(preference),
            )
            for preference in result.all()
        }

    async def list_preferences(self, user_id: UUID) -> dict[str, StoredNotificationPreference]:
        result = await self._session.scalars(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id),
        )
        return {
            preference.scenario: StoredNotificationPreference(
                enabled=preference.enabled,
                delivery_mode=NotificationDeliveryMode(preference.delivery_mode),
                channels=self._preference_channels(preference),
            )
            for preference in result.all()
        }

    async def upsert_preferences(
        self,
        *,
        user_id: UUID,
        preferences: Mapping[str, StoredNotificationPreference],
    ) -> None:
        if not preferences:
            return

        scenarios = list(preferences.keys())
        result = await self._session.scalars(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.scenario.in_(scenarios),
            ),
        )
        existing = {preference.scenario: preference for preference in result.all()}
        now = datetime.now(UTC)
        for scenario, preference_update in preferences.items():
            preference = existing.get(scenario)
            if preference is None:
                preference = NotificationPreference(
                    user_id=user_id,
                    scenario=scenario,
                    enabled=preference_update.enabled,
                    delivery_mode=preference_update.delivery_mode.value,
                    channels=self._serialize_channels(preference_update),
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(preference)
                continue
            preference.enabled = preference_update.enabled
            preference.delivery_mode = preference_update.delivery_mode.value
            preference.channels = self._serialize_channels(preference_update)
            preference.updated_at = now

    async def list_pending_digest_notifications(self, business_date: date) -> list[Notification]:
        start_at, end_at = self._business_day_utc_range(business_date)
        result = await self._session.scalars(
            select(Notification)
            .where(
                Notification.delivery_mode == NotificationDeliveryMode.daily_digest.value,
                Notification.digest_sent_at.is_(None),
                Notification.created_at >= start_at,
                Notification.created_at < end_at,
            )
            .order_by(Notification.receiver_id, Notification.scenario, Notification.created_at),
        )
        return list(result.all())

    def mark_digest_notifications_sent(
        self,
        notifications: Sequence[Notification],
        *,
        sent_at: datetime,
    ) -> None:
        for notification in notifications:
            notification.digest_sent_at = sent_at
            notification.updated_at = sent_at

    async def list_notifications(
        self,
        *,
        receiver_id: UUID,
        unread: bool | None,
        page: int,
        page_size: int,
    ) -> NotificationPage:
        conditions = [
            Notification.receiver_id == receiver_id,
            Notification.delivery_mode == NotificationDeliveryMode.real_time.value,
        ]
        if unread is True:
            conditions.append(Notification.read_at.is_(None))
        elif unread is False:
            conditions.append(Notification.read_at.is_not(None))

        total = await self._session.scalar(
            select(func.count()).select_from(Notification).where(*conditions),
        )
        result = await self._session.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
        return NotificationPage(
            items=list(result.all()),
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )

    async def get_notification(self, notification_id: UUID) -> Notification | None:
        notification = await self._session.get(Notification, notification_id)
        return notification if isinstance(notification, Notification) else None

    async def list_unread_for_update(self, receiver_id: UUID) -> list[Notification]:
        result = await self._session.scalars(
            select(Notification)
            .where(Notification.receiver_id == receiver_id, Notification.read_at.is_(None))
            .where(Notification.delivery_mode == NotificationDeliveryMode.real_time.value)
            .with_for_update(),
        )
        return list(result.all())

    async def count_unread(self, receiver_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.receiver_id == receiver_id,
                Notification.read_at.is_(None),
                Notification.delivery_mode == NotificationDeliveryMode.real_time.value,
            ),
        )
        return int(total or 0)

    def add_many(self, notifications: Sequence[Notification]) -> None:
        self._session.add_all(list(notifications))

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        for notification in notifications:
            await self._session.refresh(notification)

    async def refresh(self, notification: Notification) -> None:
        await self._session.refresh(notification)

    @staticmethod
    def _business_day_utc_range(business_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(business_date, time.min, tzinfo=BUSINESS_TIMEZONE)
        end = start + timedelta(days=1)
        return start.astimezone(UTC), end.astimezone(UTC)

    @staticmethod
    def _preference_channels(
        preference: NotificationPreference,
    ) -> dict[NotificationChannelType, bool]:
        raw_channels = getattr(preference, "channels", None)
        return normalize_channel_settings(raw_channels, in_app_default=preference.enabled)

    @staticmethod
    def _serialize_channels(preference: StoredNotificationPreference) -> dict[str, bool]:
        return {
            channel.value: enabled
            for channel, enabled in preference.normalized_channels().items()
        }


class InMemoryNotificationRepository:
    def __init__(
        self,
        notifications: Sequence[Notification] | None = None,
        preferences: Mapping[tuple[UUID, str], StoredNotificationPreference] | None = None,
    ) -> None:
        self.notifications = list(notifications or [])
        self.preferences = dict(preferences or {})

    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        requested = set(dedup_keys)
        return {
            notification.dedup_key
            for notification in self.notifications
            if notification.dedup_key in requested
        }

    async def disabled_receivers_for_scenario(
        self,
        *,
        scenario: str,
        receiver_ids: Sequence[UUID],
    ) -> set[UUID]:
        return {
            receiver_id
            for receiver_id in receiver_ids
            if not self.preferences.get((receiver_id, scenario), self._default_preference()).enabled
        }

    async def preferences_for_scenario(
        self,
        *,
        scenario: str,
        receiver_ids: Sequence[UUID],
    ) -> dict[UUID, StoredNotificationPreference]:
        requested = set(receiver_ids)
        return {
            preference_user_id: preference
            for (preference_user_id, preference_scenario), preference in self.preferences.items()
            if preference_user_id in requested and preference_scenario == scenario
        }

    async def list_preferences(self, user_id: UUID) -> dict[str, StoredNotificationPreference]:
        return {
            scenario: preference
            for (preference_user_id, scenario), preference in self.preferences.items()
            if preference_user_id == user_id
        }

    async def upsert_preferences(
        self,
        *,
        user_id: UUID,
        preferences: Mapping[str, StoredNotificationPreference],
    ) -> None:
        for scenario, preference in preferences.items():
            self.preferences[(user_id, scenario)] = preference

    async def list_pending_digest_notifications(self, business_date: date) -> list[Notification]:
        return [
            notification
            for notification in self.notifications
            if self._notification_delivery_mode(notification)
            == NotificationDeliveryMode.daily_digest
            and notification.digest_sent_at is None
            and notification.created_at.astimezone(BUSINESS_TIMEZONE).date() == business_date
        ]

    def mark_digest_notifications_sent(
        self,
        notifications: Sequence[Notification],
        *,
        sent_at: datetime,
    ) -> None:
        for notification in notifications:
            notification.digest_sent_at = sent_at
            notification.updated_at = sent_at

    async def list_notifications(
        self,
        *,
        receiver_id: UUID,
        unread: bool | None,
        page: int,
        page_size: int,
    ) -> NotificationPage:
        notifications = [
            notification
            for notification in self.notifications
            if notification.receiver_id == receiver_id
            and self._notification_delivery_mode(notification)
            == NotificationDeliveryMode.real_time
        ]
        if unread is True:
            notifications = [
                notification for notification in notifications if notification.read_at is None
            ]
        elif unread is False:
            notifications = [
                notification
                for notification in notifications
                if notification.read_at is not None
            ]
        notifications = sorted(
            notifications,
            key=lambda notification: notification.created_at,
            reverse=True,
        )
        start = (page - 1) * page_size
        return NotificationPage(
            items=notifications[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(notifications),
        )

    async def get_notification(self, notification_id: UUID) -> Notification | None:
        return next(
            (
                notification
                for notification in self.notifications
                if notification.id == notification_id
            ),
            None,
        )

    async def list_unread_for_update(self, receiver_id: UUID) -> list[Notification]:
        return [
            notification
            for notification in self.notifications
            if notification.receiver_id == receiver_id
            and notification.read_at is None
            and self._notification_delivery_mode(notification)
            == NotificationDeliveryMode.real_time
        ]

    async def count_unread(self, receiver_id: UUID) -> int:
        return len(
            [
                notification
                for notification in self.notifications
                if notification.receiver_id == receiver_id
                and notification.read_at is None
                and self._notification_delivery_mode(notification)
                == NotificationDeliveryMode.real_time
            ],
        )

    def add_many(self, notifications: Sequence[Notification]) -> None:
        self.notifications.extend(notifications)

    async def commit(self) -> None:
        return None

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        _ = notifications
        return None

    async def refresh(self, notification: Notification) -> None:
        _ = notification
        return None

    @staticmethod
    def _default_preference() -> StoredNotificationPreference:
        return StoredNotificationPreference(
            enabled=True,
            delivery_mode=NotificationDeliveryMode.real_time,
        )

    @staticmethod
    def _notification_delivery_mode(notification: Notification) -> NotificationDeliveryMode:
        value = getattr(notification, "delivery_mode", None) or NotificationDeliveryMode.real_time
        return NotificationDeliveryMode(value)


class NotificationService:
    def __init__(
        self,
        *,
        repository: NotificationRepository,
        business_date_provider: Callable[[], date] = current_business_date,
        now_provider: Callable[[], datetime] = current_utc_datetime,
        channels: Mapping[NotificationChannelType, NotificationChannel] | None = None,
        delivery_service: NotificationDeliveryService | None = None,
    ) -> None:
        self._repository = repository
        self._business_date_provider = business_date_provider
        self._now_provider = now_provider
        self._channels = dict(channels or {})
        self._delivery_service = delivery_service

    async def send(
        self,
        *,
        scenario: str,
        receivers: Sequence[UUID],
        source_id: UUID | str,
        payload: Mapping[str, object] | None = None,
    ) -> list[Notification]:
        """Create unread in-app notifications, skipping same-day duplicates."""
        receiver_ids = self._unique_receivers(receivers)
        if not receiver_ids:
            return []
        receiver_preferences = await self._preferences_for_receivers(
            scenario=scenario,
            receiver_ids=receiver_ids,
        )
        receiver_ids = [
            receiver_id
            for receiver_id in receiver_ids
            if self._has_enabled_channel(receiver_preferences[receiver_id])
        ]
        if not receiver_ids:
            return []

        source_key = str(source_id)
        business_date = self._business_date_provider()
        dedup_by_receiver = {
            receiver_id: self.build_dedup_key(
                scenario=scenario,
                receiver_id=receiver_id,
                source_id=source_key,
                business_date=business_date,
            )
            for receiver_id in receiver_ids
        }
        existing = await self._repository.existing_dedup_keys(list(dedup_by_receiver.values()))
        now = self._now_provider()
        notification_payload = dict(payload or {})
        in_app_receiver_ids = {
            receiver_id
            for receiver_id in receiver_ids
            if receiver_preferences[receiver_id].channel_enabled(NotificationChannelType.in_app)
        }

        notifications = [
            Notification(
                receiver_id=receiver_id,
                scenario=scenario,
                source_id=source_key,
                payload=notification_payload,
                dedup_key=dedup_key,
                delivery_mode=receiver_preferences[receiver_id].delivery_mode.value,
                digest_sent_at=None,
                read_at=None,
                created_at=now,
                updated_at=now,
            )
            for receiver_id, dedup_key in dedup_by_receiver.items()
            if receiver_id in in_app_receiver_ids
            if dedup_key not in existing
        ]

        if notifications:
            self._repository.add_many(notifications)
            await self._repository.commit()
            await self._repository.refresh_many(notifications)
        await self._send_external_channels(
            scenario=scenario,
            source_id=source_key,
            payload=notification_payload,
            dedup_by_receiver=dedup_by_receiver,
            receiver_preferences=receiver_preferences,
            existing_dedup_keys=existing,
        )
        return notifications

    async def list_notifications(
        self,
        *,
        actor: User,
        unread: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NotificationPage:
        self._validate_page(page=page, page_size=page_size)
        return await self._repository.list_notifications(
            receiver_id=actor.id,
            unread=unread,
            page=page,
            page_size=page_size,
        )

    async def unread_count(self, *, actor: User) -> int:
        return await self._repository.count_unread(actor.id)

    async def list_preferences(self, *, actor: User) -> list[NotificationPreferenceState]:
        stored_preferences = await self._repository.list_preferences(actor.id)
        return [
            NotificationPreferenceState(
                scenario=definition.scenario,
                label=definition.label,
                description=definition.description,
                direct_related=definition.direct_related,
                enabled=(
                    preference := stored_preferences.get(
                        definition.scenario,
                        self._default_preference(),
                    )
                ).enabled,
                delivery_mode=preference.delivery_mode,
                channels=preference.normalized_channels(),
            )
            for definition in NOTIFICATION_SCENARIOS
        ]

    async def update_preferences(
        self,
        *,
        actor: User,
        preferences: Mapping[str, StoredNotificationPreference],
    ) -> list[NotificationPreferenceState]:
        unknown_scenarios = sorted(
            set(preferences.keys()) - set(NOTIFICATION_SCENARIO_BY_CODE.keys()),
        )
        if unknown_scenarios:
            raise ValidationFailedError(
                "Unknown notification scenario",
                data={"scenarios": unknown_scenarios},
            )

        await self._repository.upsert_preferences(
            user_id=actor.id,
            preferences=preferences,
        )
        await self._repository.commit()
        return await self.list_preferences(actor=actor)

    async def generate_daily_digest(
        self,
        *,
        business_date: date | None = None,
    ) -> NotificationDigestResult:
        target_date = business_date or (self._business_date_provider() - timedelta(days=1))
        pending_notifications = await self._repository.list_pending_digest_notifications(
            target_date,
        )
        if not pending_notifications:
            return NotificationDigestResult(
                business_date=target_date,
                source_notification_count=0,
                digest_notification_count=0,
            )

        notifications_by_receiver: dict[UUID, list[Notification]] = defaultdict(list)
        for notification in pending_notifications:
            notifications_by_receiver[notification.receiver_id].append(notification)

        source_id = target_date.isoformat()
        dedup_by_receiver = {
            receiver_id: self.build_dedup_key(
                scenario=DAILY_DIGEST_SCENARIO,
                receiver_id=receiver_id,
                source_id=source_id,
                business_date=target_date,
            )
            for receiver_id in notifications_by_receiver
        }
        existing = await self._repository.existing_dedup_keys(list(dedup_by_receiver.values()))
        now = self._now_provider()
        digest_notifications = [
            Notification(
                receiver_id=receiver_id,
                scenario=DAILY_DIGEST_SCENARIO,
                source_id=source_id,
                payload=self._build_digest_payload(
                    business_date=target_date,
                    notifications=items,
                ),
                dedup_key=dedup_key,
                delivery_mode=NotificationDeliveryMode.real_time.value,
                digest_sent_at=None,
                read_at=None,
                created_at=now,
                updated_at=now,
            )
            for receiver_id, dedup_key in dedup_by_receiver.items()
            if dedup_key not in existing
            for items in [notifications_by_receiver[receiver_id]]
        ]

        if digest_notifications:
            self._repository.add_many(digest_notifications)
        self._repository.mark_digest_notifications_sent(pending_notifications, sent_at=now)
        await self._repository.commit()
        await self._repository.refresh_many(digest_notifications)
        return NotificationDigestResult(
            business_date=target_date,
            source_notification_count=len(pending_notifications),
            digest_notification_count=len(digest_notifications),
        )

    async def mark_read(self, *, actor: User, notification_id: UUID) -> Notification:
        notification = await self._get_owned_notification(
            actor=actor,
            notification_id=notification_id,
        )
        if notification.read_at is None:
            now = self._now_provider()
            notification.read_at = now
            notification.updated_at = now
            await self._repository.commit()
            await self._repository.refresh(notification)
        return notification

    async def mark_all_read(self, *, actor: User) -> int:
        notifications = await self._repository.list_unread_for_update(actor.id)
        if not notifications:
            return 0
        now = self._now_provider()
        for notification in notifications:
            notification.read_at = now
            notification.updated_at = now
        await self._repository.commit()
        await self._repository.refresh_many(notifications)
        return len(notifications)

    @staticmethod
    def build_dedup_key(
        *,
        scenario: str,
        receiver_id: UUID,
        source_id: str,
        business_date: date,
    ) -> str:
        return f"{scenario}:{receiver_id}:{source_id}:{business_date:%Y%m%d}"

    async def _get_owned_notification(
        self,
        *,
        actor: User,
        notification_id: UUID,
    ) -> Notification:
        notification = await self._repository.get_notification(notification_id)
        if notification is None or notification.receiver_id != actor.id:
            raise ResourceNotFoundError("Notification does not exist")
        return notification

    @staticmethod
    def _validate_page(*, page: int, page_size: int) -> None:
        if page < 1:
            raise ValidationFailedError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValidationFailedError("Page size must be between 1 and 100")

    async def _preferences_for_receivers(
        self,
        *,
        scenario: str,
        receiver_ids: list[UUID],
    ) -> dict[UUID, StoredNotificationPreference]:
        stored_preferences = await self._repository.preferences_for_scenario(
            scenario=scenario,
            receiver_ids=receiver_ids,
        )
        return {
            receiver_id: stored_preferences.get(receiver_id, self._default_preference())
            for receiver_id in receiver_ids
        }

    @staticmethod
    def _default_preference() -> StoredNotificationPreference:
        return StoredNotificationPreference(
            enabled=True,
            delivery_mode=NotificationDeliveryMode.real_time,
        )

    def _has_enabled_channel(self, preference: StoredNotificationPreference) -> bool:
        if preference.channel_enabled(NotificationChannelType.in_app):
            return True
        return any(preference.channel_enabled(channel) for channel in self._channels)

    async def _send_external_channels(
        self,
        *,
        scenario: str,
        source_id: str,
        payload: dict[str, object],
        dedup_by_receiver: Mapping[UUID, str],
        receiver_preferences: Mapping[UUID, StoredNotificationPreference],
        existing_dedup_keys: set[str],
    ) -> None:
        for receiver_id, dedup_key in dedup_by_receiver.items():
            if dedup_key in existing_dedup_keys:
                continue
            preference = receiver_preferences[receiver_id]
            for channel_type, channel in self._channels.items():
                if not preference.channel_enabled(channel_type):
                    continue
                message = NotificationChannelMessage(
                    channel=channel_type,
                    receiver_id=receiver_id,
                    scenario=scenario,
                    source_id=source_id,
                    payload=dict(payload),
                    dedup_key=dedup_key,
                )
                if self._delivery_service is None:
                    await channel.send(message)
                    continue
                await self._delivery_service.enqueue_and_attempt(
                    message=message,
                    channel=channel,
                )

    def _build_digest_payload(
        self,
        *,
        business_date: date,
        notifications: Sequence[Notification],
    ) -> dict[str, object]:
        grouped: dict[str, list[Notification]] = defaultdict(list)
        for notification in notifications:
            grouped[notification.scenario].append(notification)

        return {
            "business_date": business_date.isoformat(),
            "total": len(notifications),
            "groups": [
                {
                    "scenario": scenario,
                    "label": self._scenario_label(scenario),
                    "count": len(items),
                    "items": [
                        {
                            "id": str(item.id),
                            "source_id": item.source_id,
                            "created_at": item.created_at.isoformat(),
                            "payload": dict(item.payload),
                        }
                        for item in sorted(items, key=lambda item: item.created_at)
                    ],
                }
                for scenario, items in sorted(grouped.items())
            ],
        }

    @staticmethod
    def _scenario_label(scenario: str) -> str:
        definition = NOTIFICATION_SCENARIO_BY_CODE.get(scenario)
        return definition.label if definition is not None else scenario

    @staticmethod
    def _unique_receivers(receivers: Sequence[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        unique_receivers: list[UUID] = []
        for receiver_id in receivers:
            if receiver_id in seen:
                continue
            seen.add(receiver_id)
            unique_receivers.append(receiver_id)
        return unique_receivers
