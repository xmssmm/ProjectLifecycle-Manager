from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.models.api_keys import ApiKey
from app.models.users import User, UserRole
from app.schemas.api_keys import API_KEY_PERMISSIONS, ApiKeyCreate


@dataclass(frozen=True)
class ApiKeyCreateResult:
    api_key: ApiKey
    token: str


class ApiKeyRepository(Protocol):
    async def list_keys(self, *, page: int, page_size: int) -> tuple[list[ApiKey], int]:
        ...

    async def get_by_id_for_update(self, api_key_id: UUID) -> ApiKey | None:
        ...

    async def get_by_hash_for_update(self, key_hash: str) -> ApiKey | None:
        ...

    def add(self, api_key: ApiKey) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, api_key: ApiKey) -> None:
        ...


class SqlAlchemyApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_keys(self, *, page: int, page_size: int) -> tuple[list[ApiKey], int]:
        total = await self._session.scalar(select(func.count()).select_from(ApiKey))
        statement = (
            select(ApiKey)
            .order_by(ApiKey.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        keys = list((await self._session.scalars(statement)).all())
        return keys, int(total or 0)

    async def get_by_id_for_update(self, api_key_id: UUID) -> ApiKey | None:
        result = await self._session.scalar(
            select(ApiKey).where(ApiKey.id == api_key_id).with_for_update(),
        )
        return result

    async def get_by_hash_for_update(self, key_hash: str) -> ApiKey | None:
        result = await self._session.scalar(
            select(ApiKey).where(ApiKey.key_hash == key_hash).with_for_update(),
        )
        return result

    def add(self, api_key: ApiKey) -> None:
        self._session.add(api_key)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, api_key: ApiKey) -> None:
        await self._session.refresh(api_key)


class InMemoryApiKeyRepository:
    def __init__(self, api_keys: Sequence[ApiKey] | None = None) -> None:
        self.api_keys = list(api_keys or [])

    async def list_keys(self, *, page: int, page_size: int) -> tuple[list[ApiKey], int]:
        ordered = sorted(self.api_keys, key=lambda key: key.created_at, reverse=True)
        start = (page - 1) * page_size
        return ordered[start : start + page_size], len(ordered)

    async def get_by_id_for_update(self, api_key_id: UUID) -> ApiKey | None:
        return next((key for key in self.api_keys if key.id == api_key_id), None)

    async def get_by_hash_for_update(self, key_hash: str) -> ApiKey | None:
        return next((key for key in self.api_keys if key.key_hash == key_hash), None)

    def add(self, api_key: ApiKey) -> None:
        self.api_keys.append(api_key)

    async def commit(self) -> None:
        return None

    async def refresh(self, api_key: ApiKey) -> None:
        _ = api_key
        return None


class ApiKeyService:
    def __init__(
        self,
        *,
        repository: ApiKeyRepository,
        now_provider: Callable[[], datetime] | None = None,
        token_generator: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._token_generator = token_generator or self._generate_token

    async def list_keys(
        self,
        *,
        actor: User,
        page: int,
        page_size: int,
    ) -> tuple[list[ApiKey], int]:
        self._ensure_admin(actor)
        return await self._repository.list_keys(page=page, page_size=page_size)

    async def create_key(self, *, actor: User, payload: ApiKeyCreate) -> ApiKeyCreateResult:
        self._ensure_admin(actor)
        permissions = self._normalize_permissions(payload.permissions)
        token = self._token_generator()
        now = self._now_provider()
        api_key = ApiKey(
            name=payload.name,
            key_prefix=token[:12],
            key_hash=hash_api_key_token(token),
            permissions=permissions,
            expires_at=payload.expires_at,
            last_used_at=None,
            revoked_at=None,
            created_by_id=actor.id,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(api_key)
        await self._repository.commit()
        await self._repository.refresh(api_key)
        return ApiKeyCreateResult(api_key=api_key, token=token)

    async def revoke_key(self, *, actor: User, api_key_id: UUID) -> ApiKey:
        self._ensure_admin(actor)
        api_key = await self._get_existing_key(api_key_id)
        now = self._now_provider()
        if api_key.revoked_at is None:
            api_key.revoked_at = now
            api_key.updated_at = now
            await self._repository.commit()
            await self._repository.refresh(api_key)
        return api_key

    async def authenticate(
        self,
        *,
        token: str,
        required_permission: str | None = None,
    ) -> ApiKey:
        api_key = await self._repository.get_by_hash_for_update(hash_api_key_token(token))
        if api_key is None:
            raise AuthenticationError("Invalid API key")
        now = self._now_provider()
        if api_key.revoked_at is not None:
            raise AuthenticationError("API key has been revoked")
        if api_key.expires_at is not None and api_key.expires_at <= now:
            raise AuthenticationError("API key has expired")
        if required_permission is not None and required_permission not in api_key.permissions:
            raise PermissionDeniedError("API key permission is insufficient")
        api_key.last_used_at = now
        api_key.updated_at = now
        await self._repository.commit()
        await self._repository.refresh(api_key)
        return api_key

    async def _get_existing_key(self, api_key_id: UUID) -> ApiKey:
        api_key = await self._repository.get_by_id_for_update(api_key_id)
        if api_key is None:
            raise ResourceNotFoundError("API key does not exist")
        return api_key

    @staticmethod
    def _ensure_admin(actor: User) -> None:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()

    @staticmethod
    def _normalize_permissions(permissions: Sequence[str]) -> list[str]:
        normalized = list(dict.fromkeys(permissions))
        unknown = sorted(set(normalized) - API_KEY_PERMISSIONS)
        if not normalized or unknown:
            raise ValidationFailedError(
                "API key permissions are invalid",
                data={"allowed": sorted(API_KEY_PERMISSIONS), "unknown": unknown},
            )
        return normalized

    @staticmethod
    def _generate_token() -> str:
        return f"mgmt_{secrets.token_urlsafe(32)}"


def hash_api_key_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
