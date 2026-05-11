from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AiAuditLog, AiAuditStatus

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"\b\d{17}[\dXx]\b"),
)


@dataclass(frozen=True)
class AiAuditEntry:
    actor_id: UUID | None
    error_code: str | None
    error_message: str | None
    id: UUID
    model: str | None
    prompt_summary: dict[str, object]
    provider: str
    purpose: str
    schema_name: str
    status: str
    token_estimate: int
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "created_at": self.created_at.isoformat(),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "id": str(self.id),
            "model": self.model,
            "prompt_summary": self.prompt_summary,
            "provider": self.provider,
            "purpose": self.purpose,
            "schema_name": self.schema_name,
            "status": self.status,
            "token_estimate": self.token_estimate,
        }


class AiAuditLogRepository(Protocol):
    async def add(self, entry: AiAuditEntry) -> None: ...


class InMemoryAiAuditLogRepository:
    def __init__(self) -> None:
        self.entries: list[AiAuditEntry] = []

    async def add(self, entry: AiAuditEntry) -> None:
        self.entries.append(entry)


class SqlAlchemyAiAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AiAuditEntry) -> None:
        self._session.add(
            AiAuditLog(
                id=entry.id,
                actor_id=entry.actor_id,
                purpose=entry.purpose,
                provider=entry.provider,
                model=entry.model,
                schema_name=entry.schema_name,
                prompt_summary=entry.prompt_summary,
                token_estimate=entry.token_estimate,
                status=AiAuditStatus(entry.status),
                error_code=entry.error_code,
                error_message=entry.error_message,
                created_at=entry.created_at,
                updated_at=entry.created_at,
            ),
        )
        await self._session.commit()


class AiAuditLogger:
    def __init__(
        self,
        repository: AiAuditLogRepository,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._now_provider = now_provider

    async def record(
        self,
        *,
        actor_id: UUID | None,
        error_code: str | None = None,
        error_message: str | None = None,
        model: str | None,
        prompt: str,
        provider: str,
        purpose: str,
        schema_name: str,
        status: str,
    ) -> AiAuditEntry:
        entry = AiAuditEntry(
            actor_id=actor_id,
            created_at=self._now_provider(),
            error_code=error_code,
            error_message=_redact(error_message or "")[:500] if error_message else None,
            id=uuid4(),
            model=model,
            prompt_summary=summarize_prompt(prompt),
            provider=provider,
            purpose=purpose,
            schema_name=schema_name,
            status=status,
            token_estimate=estimate_tokens(prompt),
        )
        await self._repository.add(entry)
        return entry


def summarize_prompt(prompt: str) -> dict[str, object]:
    redacted = _redact(prompt).strip()
    return {
        "length": len(prompt),
        "preview": redacted[:160],
    }


def estimate_tokens(prompt: str) -> int:
    return max(1, len(prompt) // 4)


def _redact(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
