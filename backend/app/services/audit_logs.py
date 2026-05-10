from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import PermissionDeniedError, ValidationFailedError
from app.models.audit_logs import AuditLog
from app.models.users import User, UserRole


@dataclass(frozen=True)
class AuditLogQuery:
    actor_id: UUID | None = None
    action: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class AuditLogPage:
    items: list[AuditLog]
    page: int
    page_size: int
    total: int


class AuditLogRepository(Protocol):
    async def list_logs(self, query: AuditLogQuery) -> AuditLogPage:
        ...


class SqlAlchemyAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_logs(self, query: AuditLogQuery) -> AuditLogPage:
        conditions = build_audit_log_conditions(query)
        total = await self._session.scalar(
            select(func.count()).select_from(AuditLog).where(*conditions),
        )
        result = await self._session.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size),
        )
        return AuditLogPage(
            items=list(result.all()),
            page=query.page,
            page_size=query.page_size,
            total=int(total or 0),
        )


class InMemoryAuditLogRepository:
    def __init__(self, logs: list[AuditLog] | None = None) -> None:
        self.logs = list(logs or [])

    async def list_logs(self, query: AuditLogQuery) -> AuditLogPage:
        logs = [
            log
            for log in self.logs
            if matches_audit_log_query(log=log, query=query)
        ]
        logs = sorted(logs, key=lambda log: log.created_at, reverse=True)
        start = (query.page - 1) * query.page_size
        return AuditLogPage(
            items=logs[start : start + query.page_size],
            page=query.page,
            page_size=query.page_size,
            total=len(logs),
        )


class AuditLogService:
    def __init__(self, *, repository: AuditLogRepository) -> None:
        self._repository = repository

    async def list_logs(self, *, actor: User, query: AuditLogQuery) -> AuditLogPage:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError("Permission denied")
        self._validate_page(query)
        return await self._repository.list_logs(query)

    @staticmethod
    def _validate_page(query: AuditLogQuery) -> None:
        if query.page < 1:
            raise ValidationFailedError("Page must be greater than or equal to 1")
        if query.page_size < 1 or query.page_size > 100:
            raise ValidationFailedError("Page size must be between 1 and 100")


def build_audit_log_conditions(query: AuditLogQuery) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if query.actor_id is not None:
        conditions.append(AuditLog.actor_id == query.actor_id)
    if query.action is not None:
        conditions.append(AuditLog.action == query.action)
    if query.target_type is not None:
        conditions.append(AuditLog.target_type == query.target_type)
    if query.target_id is not None:
        conditions.append(AuditLog.target_id == query.target_id)
    if query.created_from is not None:
        conditions.append(AuditLog.created_at >= query.created_from)
    if query.created_to is not None:
        conditions.append(AuditLog.created_at <= query.created_to)
    return conditions


def matches_audit_log_query(*, log: AuditLog, query: AuditLogQuery) -> bool:
    if query.actor_id is not None and log.actor_id != query.actor_id:
        return False
    if query.action is not None and log.action != query.action:
        return False
    if query.target_type is not None and log.target_type != query.target_type:
        return False
    if query.target_id is not None and log.target_id != query.target_id:
        return False
    if query.created_from is not None and log.created_at < query.created_from:
        return False
    if query.created_to is not None and log.created_at > query.created_to:
        return False
    return True
