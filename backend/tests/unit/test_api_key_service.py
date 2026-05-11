from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.api_keys import get_api_key_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.api_keys import ApiKey
from app.models.users import User, UserRole, UserStatus
from app.schemas.api_keys import ApiKeyCreate
from app.services.api_keys import ApiKeyCreateResult, ApiKeyService, InMemoryApiKeyRepository

NOW = datetime(2026, 5, 11, 8, 0, tzinfo=UTC)


def make_user(role: UserRole, *, username: str = "admin") -> User:
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=NOW,
        last_login_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_service(*, token: str = "mgmt_test_plain_token") -> tuple[
    ApiKeyService,
    InMemoryApiKeyRepository,
]:
    repository = InMemoryApiKeyRepository()
    service = ApiKeyService(
        repository=repository,
        now_provider=lambda: NOW,
        token_generator=lambda: token,
    )
    return service, repository


@pytest.mark.asyncio
async def test_create_returns_plain_token_once_and_stores_only_hash() -> None:
    admin = make_user(UserRole.admin)
    service, repository = make_service()

    result = await service.create_key(
        actor=admin,
        payload=ApiKeyCreate(
            name="Reporting",
            permissions=["projects:read", "payments:read"],
            expires_at=NOW + timedelta(days=30),
        ),
    )
    listed_keys, total = await service.list_keys(actor=admin, page=1, page_size=20)

    assert result.token == "mgmt_test_plain_token"
    assert total == 1
    assert listed_keys == [result.api_key]
    assert repository.api_keys[0].key_hash != result.token
    assert result.token not in repository.api_keys[0].key_hash


@pytest.mark.asyncio
async def test_expired_and_revoked_keys_are_rejected_immediately() -> None:
    admin = make_user(UserRole.admin)
    service, _repository = make_service(token="mgmt_expired_token")
    expired = await service.create_key(
        actor=admin,
        payload=ApiKeyCreate(
            name="Expired",
            permissions=["projects:read"],
            expires_at=NOW - timedelta(seconds=1),
        ),
    )

    with pytest.raises(AuthenticationError):
        await service.authenticate(
            token=expired.token,
            required_permission="projects:read",
        )

    active_service, _active_repository = make_service(token="mgmt_revoked_token")
    active = await active_service.create_key(
        actor=admin,
        payload=ApiKeyCreate(
            name="Revoked",
            permissions=["projects:read"],
            expires_at=NOW + timedelta(days=1),
        ),
    )
    await active_service.revoke_key(actor=admin, api_key_id=active.api_key.id)

    with pytest.raises(AuthenticationError):
        await active_service.authenticate(
            token=active.token,
            required_permission="projects:read",
        )


@pytest.mark.asyncio
async def test_permission_scope_is_enforced() -> None:
    admin = make_user(UserRole.admin)
    service, _repository = make_service()
    result = await service.create_key(
        actor=admin,
        payload=ApiKeyCreate(
            name="Payments only",
            permissions=["payments:read"],
            expires_at=NOW + timedelta(days=1),
        ),
    )

    with pytest.raises(PermissionDeniedError):
        await service.authenticate(
            token=result.token,
            required_permission="projects:read",
        )


def test_api_key_endpoints_return_token_only_on_create() -> None:
    admin = make_user(UserRole.admin)
    key = ApiKey(
        id=uuid4(),
        name="Reporting",
        key_prefix="mgmt_test",
        key_hash="hashed",
        permissions=["projects:read"],
        expires_at=NOW + timedelta(days=30),
        last_used_at=None,
        revoked_at=None,
        created_by_id=admin.id,
        created_at=NOW,
        updated_at=NOW,
    )

    class FakeApiKeyService:
        async def list_keys(
            self,
            *,
            actor: User,
            page: int,
            page_size: int,
        ) -> tuple[list[ApiKey], int]:
            assert actor.id == admin.id
            assert page == 1
            assert page_size == 20
            return [key], 1

        async def create_key(
            self,
            *,
            actor: User,
            payload: ApiKeyCreate,
        ) -> ApiKeyCreateResult:
            assert actor.id == admin.id
            assert payload.name == "Reporting"
            return ApiKeyCreateResult(api_key=key, token="mgmt_plain_once")

        async def revoke_key(self, *, actor: User, api_key_id: UUID) -> ApiKey:
            assert actor.id == admin.id
            assert api_key_id == key.id
            key.revoked_at = NOW
            return key

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return admin

    async def fake_service() -> FakeApiKeyService:
        return FakeApiKeyService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_api_key_service] = fake_service
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/api-keys",
        json={
            "expires_at": (NOW + timedelta(days=30)).isoformat(),
            "name": "Reporting",
            "permissions": ["projects:read"],
        },
    )
    list_response = client.get("/api/v1/api-keys")
    revoke_response = client.delete(f"/api/v1/api-keys/{key.id}")

    assert create_response.status_code == 200
    assert create_response.json()["data"]["token"] == "mgmt_plain_once"
    assert "key_hash" not in create_response.json()["data"]["api_key"]
    assert list_response.status_code == 200
    assert "token" not in list_response.json()["data"]["items"][0]
    assert list_response.json()["data"]["items"][0]["key_prefix"] == "mgmt_test"
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["revoked_at"] is not None
