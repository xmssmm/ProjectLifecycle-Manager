from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from datetime import date
from functools import wraps
from typing import ParamSpec, Protocol, TypeVar, cast
from uuid import UUID

from fastapi import BackgroundTasks
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.audit_logs import AuditLog

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True)
class AuditContext:
    actor_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class AuditLogEntry:
    actor_id: UUID | None
    action: str
    target_type: str
    target_id: str
    before_state: dict[str, object]
    after_state: dict[str, object]
    ip_address: str | None
    user_agent: str | None
    extra: dict[str, object]
    request_id: str | None


@dataclass(frozen=True)
class AuditPartitionSpec:
    name: str
    start: date
    end: date


class AuditLogWriter(Protocol):
    def enqueue(self, entry: AuditLogEntry) -> None:
        ...


class InMemoryAuditLogWriter:
    def __init__(self) -> None:
        self.entries: list[AuditLogEntry] = []

    def enqueue(self, entry: AuditLogEntry) -> None:
        self.entries.append(entry)


class BackgroundAuditLogWriter:
    def __init__(
        self,
        *,
        background_tasks: BackgroundTasks,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._background_tasks = background_tasks
        self._session_factory = session_factory

    def enqueue(self, entry: AuditLogEntry) -> None:
        self._background_tasks.add_task(write_audit_log, self._session_factory, entry)


_audit_context_storage: ContextVar[AuditContext | None] = ContextVar(
    "audit_context",
    default=None,
)


def bind_audit_context(context: AuditContext) -> Token[AuditContext | None]:
    return _audit_context_storage.set(context)


def reset_audit_context(token: Token[AuditContext | None]) -> None:
    _audit_context_storage.reset(token)


def get_audit_context() -> AuditContext | None:
    return _audit_context_storage.get()


def set_audit_actor(actor_id: UUID | None) -> None:
    context = get_audit_context()
    if context is None:
        _audit_context_storage.set(AuditContext(actor_id=actor_id))
        return
    _audit_context_storage.set(replace(context, actor_id=actor_id))


async def write_audit_log(
    session_factory: async_sessionmaker[AsyncSession],
    entry: AuditLogEntry,
) -> None:
    async with session_factory() as session:
        session.add(
            AuditLog(
                actor_id=entry.actor_id,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                before_state=entry.before_state,
                after_state=entry.after_state,
                ip_address=entry.ip_address,
                user_agent=entry.user_agent,
                extra=entry.extra,
                request_id=entry.request_id,
            ),
        )
        await session.commit()


def audited(
    action: str,
    *,
    target_type: str | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            kwargs_lookup = cast(dict[str, object], kwargs)
            writer = _resolve_writer(args, kwargs_lookup)
            context = _resolve_context(kwargs_lookup)
            before_state = to_audit_state(kwargs_lookup.get("audit_before_state"))

            result = await func(*args, **kwargs)
            after_state = to_audit_state(result)
            extra = to_audit_state(kwargs_lookup.get("audit_extra"))
            modified_fields = build_modified_fields(before_state, after_state)
            if modified_fields:
                extra["modified_fields"] = modified_fields

            writer.enqueue(
                AuditLogEntry(
                    actor_id=context.actor_id,
                    action=action,
                    target_type=target_type or action.split(".", maxsplit=1)[0],
                    target_id=_resolve_target_id(before_state, after_state, kwargs_lookup),
                    before_state=before_state,
                    after_state=after_state,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    extra=extra,
                    request_id=context.request_id,
                ),
            )
            return result

        return wrapper

    return decorator


def build_monthly_partition_specs(
    on_date: date,
    *,
    months_ahead: int = 12,
) -> list[AuditPartitionSpec]:
    start = date(on_date.year, on_date.month, 1)
    return [
        AuditPartitionSpec(
            name=f"audit_logs_{_add_months(start, offset):%Y%m}",
            start=_add_months(start, offset),
            end=_add_months(start, offset + 1),
        )
        for offset in range(months_ahead + 1)
    ]


def to_audit_state(value: object | None) -> dict[str, object]:
    if value is None:
        return {}

    encoded = jsonable_encoder(value)
    if isinstance(encoded, dict):
        return cast(dict[str, object], encoded)
    return {"value": encoded}


def build_modified_fields(
    before_state: dict[str, object],
    after_state: dict[str, object],
) -> dict[str, dict[str, object | None]]:
    changed: dict[str, dict[str, object | None]] = {}
    for field_name in sorted(before_state.keys() | after_state.keys()):
        before_value = before_state.get(field_name)
        after_value = after_state.get(field_name)
        if before_value != after_value:
            changed[field_name] = {"before": before_value, "after": after_value}
    return changed


def _resolve_writer(args: tuple[object, ...], kwargs: dict[str, object]) -> AuditLogWriter:
    candidate = kwargs.get("audit_writer")
    if candidate is None and args:
        candidate = getattr(args[0], "audit_writer", None)
    if candidate is None or not hasattr(candidate, "enqueue"):
        raise RuntimeError("audited function requires an audit_writer")
    return cast(AuditLogWriter, candidate)


def _resolve_context(kwargs: dict[str, object]) -> AuditContext:
    candidate = kwargs.get("audit_context")
    if isinstance(candidate, AuditContext):
        return candidate
    return get_audit_context() or AuditContext()


def _resolve_target_id(
    before_state: dict[str, object],
    after_state: dict[str, object],
    kwargs: dict[str, object],
) -> str:
    for value in (
        after_state.get("id"),
        before_state.get("id"),
        kwargs.get("target_id"),
        kwargs.get("id"),
    ):
        if value is not None:
            return str(value)
    return "unknown"


def _add_months(start: date, offset: int) -> date:
    zero_based_month = start.month - 1 + offset
    year = start.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    return date(year, month, 1)
