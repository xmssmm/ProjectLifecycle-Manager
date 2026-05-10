from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import get_auth_failure_store
from app.core.config import Settings
from app.core.db import get_db_session
from app.core.exceptions import AuthenticationError, BusinessException
from app.core.middleware import InMemoryRateLimitStore
from app.core.security import decode_jwt_token, hash_password, validate_password_strength
from app.main import create_app
from app.models.users import User, UserRole, UserStatus
from app.services.auth import InMemoryAuthFailureStore, authenticate_user


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://example:example@localhost/example",
        redis_url="redis://localhost:6379/15",
        jwt_algorithm="HS256",
        jwt_secret_key="test-secret",
    )


def make_user(
    *,
    password: str = "StrongPass1!",
    status: UserStatus = UserStatus.active,
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username="admin",
        email="admin@example.local",
        password_hash=hash_password(password),
        role=UserRole.admin,
        dept_id=None,
        status=status,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def test_password_strength_validator_accepts_required_complexity() -> None:
    validate_password_strength("StrongPass1!")


@pytest.mark.parametrize(
    "password",
    ["short1!", "missing-number!", "MISSINGLOWER1!", "missingupper1!", "MissingSpecial1"],
)
def test_password_strength_validator_rejects_weak_passwords(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_strength(password)


@pytest.mark.asyncio
async def test_authenticate_user_success_returns_access_and_refresh_tokens() -> None:
    settings = make_settings()
    user = make_user()
    store = InMemoryAuthFailureStore()

    tokens = await authenticate_user(
        user=user,
        password="StrongPass1!",
        failure_store=store,
        settings=settings,
    )

    assert tokens.access_token
    assert tokens.refresh_token
    claims = decode_jwt_token(
        tokens.access_token,
        key=settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert claims["sub"] == str(user.id)
    assert claims["type"] == "access"
    assert claims["role"] == UserRole.admin.value
    assert await store.get_fail_count(f"auth:fail:{user.id}") == 0
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_authenticate_user_allows_password_reset_required_users_to_login() -> None:
    settings = make_settings()
    user = make_user(status=UserStatus.password_reset_required)
    store = InMemoryAuthFailureStore()

    tokens = await authenticate_user(
        user=user,
        password="StrongPass1!",
        failure_store=store,
        settings=settings,
    )

    assert tokens.access_token
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password_increments_failure_counter() -> None:
    settings = make_settings()
    user = make_user()
    store = InMemoryAuthFailureStore()

    with pytest.raises(AuthenticationError):
        await authenticate_user(
            user=user,
            password="wrong",
            failure_store=store,
            settings=settings,
        )

    assert await store.get_fail_count(f"auth:fail:{user.id}") == 1


@pytest.mark.asyncio
async def test_authenticate_user_locks_after_five_failures_and_unlocks_after_reset() -> None:
    settings = make_settings()
    user = make_user()
    store = InMemoryAuthFailureStore()

    for _ in range(4):
        with pytest.raises(AuthenticationError):
            await authenticate_user(
                user=user,
                password="wrong",
                failure_store=store,
                settings=settings,
            )

    with pytest.raises(BusinessException) as locked:
        await authenticate_user(
            user=user,
            password="wrong",
            failure_store=store,
            settings=settings,
        )
    assert locked.value.status_code == 423
    assert await store.get_fail_count(f"auth:fail:{user.id}") == 5

    with pytest.raises(BusinessException) as still_locked:
        await authenticate_user(
            user=user,
            password="StrongPass1!",
            failure_store=store,
            settings=settings,
        )
    assert still_locked.value.status_code == 423

    await store.reset_fail_count(f"auth:fail:{user.id}")
    tokens = await authenticate_user(
        user=user,
        password="StrongPass1!",
        failure_store=store,
        settings=settings,
    )
    assert tokens.access_token


def test_login_endpoint_returns_tokens_and_refresh_cookie() -> None:
    settings = make_settings()
    user = make_user()
    store = InMemoryAuthFailureStore()

    class FakeSession:
        async def scalar(self, _statement: object) -> User:
            return user

        async def commit(self) -> None:
            return None

    async def fake_db_session() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    async def healthy_components() -> dict[str, str]:
        return {}

    app = create_app(
        settings=settings,
        rate_limit_store=InMemoryRateLimitStore(),
        auth_failure_store=store,
        health_checker=healthy_components,
    )
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_auth_failure_store] = lambda: store
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["access_token"]
    assert payload["data"]["refresh_token"]
    assert response.cookies.get("refresh_token") == payload["data"]["refresh_token"]
