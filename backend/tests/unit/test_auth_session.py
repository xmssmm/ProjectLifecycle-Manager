from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import get_db_session
from app.core.deps import get_auth_token_store
from app.core.exceptions import AuthenticationError
from app.core.middleware import InMemoryRateLimitStore
from app.core.security import create_jwt_token, hash_password
from app.main import create_app
from app.models.users import User, UserRole, UserStatus
from app.services.auth import (
    InMemoryAuthFailureStore,
    InMemoryAuthTokenStore,
    create_auth_tokens,
    validate_token_claims,
)


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://example:example@localhost/example",
        redis_url="redis://localhost:6379/15",
        jwt_algorithm="HS256",
        jwt_secret_key="test-secret",
    )


def make_user() -> User:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        username="admin",
        email="admin@example.local",
        password_hash=hash_password("StrongPass1!"),
        role=UserRole.admin,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )
    user.timezone = "America/Los_Angeles"
    return user


def tamper_jwt_payload(token: str) -> str:
    header, payload, signature = token.split(".")
    padded_payload = payload + "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(padded_payload))
    claims["role"] = UserRole.proj_member.value
    tampered_payload = (
        base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":")).encode("utf-8"),
        )
        .decode("ascii")
        .rstrip("=")
    )
    return ".".join((header, tampered_payload, signature))


class FakeSession:
    def __init__(self, user: User) -> None:
        self.user = user

    async def scalar(self, _statement: object) -> User:
        return self.user

    async def get(self, _model: object, user_id: UUID) -> User | None:
        return self.user if self.user.id == user_id else None

    async def commit(self) -> None:
        return None


def build_auth_client(
    *,
    user: User,
    settings: Settings,
    token_store: InMemoryAuthTokenStore,
) -> TestClient:
    async def fake_db_session() -> AsyncIterator[FakeSession]:
        yield FakeSession(user)

    async def healthy_components() -> dict[str, str]:
        return {}

    app = create_app(
        settings=settings,
        rate_limit_store=InMemoryRateLimitStore(),
        auth_failure_store=InMemoryAuthFailureStore(),
        auth_token_store=token_store,
        health_checker=healthy_components,
    )
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_auth_token_store] = lambda: token_store
    return TestClient(app)


def test_refresh_me_logout_and_blacklisted_access_token_flow() -> None:
    settings = make_settings()
    user = make_user()
    token_store = InMemoryAuthTokenStore()
    client = build_auth_client(user=user, settings=settings, token_store=token_store)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPass1!"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["data"]["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"] == {
        "id": str(user.id),
        "username": "admin",
        "email": "admin@example.local",
        "role": UserRole.admin.value,
        "dept_id": None,
        "status": UserStatus.active.value,
        "timezone": "America/Los_Angeles",
    }

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["data"]["access_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 200
    assert logout_response.cookies.get("refresh_token") is None

    blocked_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert blocked_response.status_code == 401


@pytest.mark.asyncio
async def test_user_wide_token_revocation_rejects_existing_access_tokens() -> None:
    settings = make_settings()
    user = make_user()
    token_store = InMemoryAuthTokenStore()
    tokens = create_auth_tokens(user, settings)

    await validate_token_claims(
        tokens.access_token,
        expected_type="access",
        token_store=token_store,
        settings=settings,
    )
    await token_store.revoke_user_tokens(str(user.id), ttl_seconds=60 * 60)

    with pytest.raises(AuthenticationError):
        await validate_token_claims(
            tokens.access_token,
            expected_type="access",
            token_store=token_store,
            settings=settings,
        )


@pytest.mark.asyncio
async def test_validate_token_claims_rejects_tampered_and_expired_tokens() -> None:
    settings = make_settings()
    user = make_user()
    token_store = InMemoryAuthTokenStore()
    tokens = create_auth_tokens(user, settings)
    tampered = tamper_jwt_payload(tokens.access_token)
    expired = create_jwt_token(
        subject=str(user.id),
        key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        token_type="access",
        expires_delta=timedelta(seconds=-1),
        extra_claims={"role": user.role.value, "username": user.username},
    )

    for token in (tampered, expired):
        with pytest.raises(AuthenticationError):
            await validate_token_claims(
                token,
                expected_type="access",
                token_store=token_store,
                settings=settings,
            )
