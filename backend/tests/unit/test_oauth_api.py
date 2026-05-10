from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.oauth import get_oauth_service
from app.core.config import Settings
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.core.security import decode_jwt_token, hash_password
from app.main import create_app
from app.models.oauth import OAuthBinding
from app.models.users import User, UserRole, UserStatus
from app.services.auth import InMemoryAuthFailureStore, InMemoryAuthTokenStore
from app.services.oauth import OAuthAuthorizationStart, OAuthExternalIdentity, OAuthProviderConfig


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://example:example@localhost/example",
        redis_url="redis://localhost:6379/15",
        jwt_algorithm="HS256",
        jwt_secret_key="test-secret",
    )


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
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


def make_binding(user: User) -> OAuthBinding:
    now = datetime.now(UTC)
    return OAuthBinding(
        id=uuid4(),
        user_id=user.id,
        provider="generic_oidc",
        external_id="external-user-1",
        email="admin@example.local",
        access_token_ciphertext="access-token",
        refresh_token_ciphertext="refresh-token",
        expires_at=None,
        created_at=now,
        updated_at=now,
    )


class FakeOAuthService:
    def __init__(self, user: User) -> None:
        self.user = user
        self.binding = make_binding(user)
        self.started_providers: list[str] = []
        self.callbacks: list[tuple[str, str, str]] = []
        self.bound_user_ids: list[UUID] = []
        self.deleted_bindings: list[tuple[UUID, str]] = []

    def list_providers(self) -> Sequence[OAuthProviderConfig]:
        return [
            OAuthProviderConfig(
                provider="generic_oidc",
                client_id="client-id",
                client_secret="client-secret",
                authorize_url="https://sso.example.local/oauth/authorize",
                token_url="https://sso.example.local/oauth/token",
                userinfo_url="https://sso.example.local/oauth/userinfo",
                redirect_uri="https://app.example.local/login?oauth_provider=generic_oidc",
                scope="openid email profile",
                label="企业账号",
            ),
        ]

    async def start_login(
        self,
        provider: str,
        *,
        purpose: str = "login",
    ) -> OAuthAuthorizationStart:
        _ = purpose
        self.started_providers.append(provider)
        return OAuthAuthorizationStart(
            authorization_url="https://sso.example.local/oauth/authorize?state=state-1",
            state="state-1",
        )

    async def handle_callback(
        self,
        *,
        provider: str,
        code: str,
        state: str,
    ) -> OAuthExternalIdentity:
        self.callbacks.append((provider, code, state))
        return OAuthExternalIdentity(
            provider=provider,
            external_id="external-user-1",
            email="admin@example.local",
            email_verified=True,
            display_name="Admin",
            bound_user_id=self.user.id,
            access_token_ciphertext="oauth-access-token",
            refresh_token_ciphertext="oauth-refresh-token",
            expires_at=None,
        )

    async def resolve_login_user(self, identity: OAuthExternalIdentity) -> User:
        assert identity.bound_user_id == self.user.id
        return self.user

    async def list_user_bindings(self, user_id: UUID) -> list[OAuthBinding]:
        return [self.binding] if user_id == self.user.id else []

    async def bind_identity(self, *, user: User, identity: OAuthExternalIdentity) -> OAuthBinding:
        self.bound_user_ids.append(user.id)
        return self.binding

    async def delete_user_binding(self, *, user_id: UUID, provider: str) -> bool:
        self.deleted_bindings.append((user_id, provider))
        return True


def build_client() -> tuple[TestClient, FakeOAuthService, Settings, User]:
    settings = make_settings()
    user = make_user()
    service = FakeOAuthService(user)

    async def healthy_components() -> dict[str, str]:
        return {}

    app = create_app(
        settings=settings,
        rate_limit_store=InMemoryRateLimitStore(),
        auth_failure_store=InMemoryAuthFailureStore(),
        auth_token_store=InMemoryAuthTokenStore(),
        health_checker=healthy_components,
    )
    app.dependency_overrides[get_oauth_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), service, settings, user


def test_oauth_provider_login_callback_and_binding_routes() -> None:
    client, service, settings, user = build_client()

    providers_response = client.get("/api/v1/oauth/providers")
    assert providers_response.status_code == 200
    assert providers_response.json()["data"] == [
        {"provider": "generic_oidc", "label": "企业账号"},
    ]

    login_response = client.get("/api/v1/oauth/generic_oidc/login")
    assert login_response.status_code == 200
    assert login_response.json()["data"] == {
        "authorization_url": "https://sso.example.local/oauth/authorize?state=state-1",
        "state": "state-1",
    }
    assert service.started_providers == ["generic_oidc"]

    callback_response = client.get(
        "/api/v1/oauth/generic_oidc/callback",
        params={"code": "code-1", "state": "state-1"},
    )
    assert callback_response.status_code == 200
    callback_payload = callback_response.json()["data"]
    assert callback_payload["access_token"]
    assert callback_payload["refresh_token"]
    assert callback_response.cookies.get("refresh_token") == callback_payload["refresh_token"]
    claims = decode_jwt_token(
        callback_payload["access_token"],
        key=settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert claims["sub"] == str(user.id)
    assert service.callbacks == [("generic_oidc", "code-1", "state-1")]

    bindings_response = client.get("/api/v1/oauth/bindings")
    assert bindings_response.status_code == 200
    assert bindings_response.json()["data"][0]["provider"] == "generic_oidc"

    bind_response = client.post(
        "/api/v1/oauth/generic_oidc/bind",
        json={"code": "bind-code", "state": "bind-state"},
    )
    assert bind_response.status_code == 200
    assert bind_response.json()["data"]["external_id"] == "external-user-1"
    assert service.bound_user_ids == [user.id]

    delete_response = client.delete("/api/v1/oauth/generic_oidc/bind")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"unbound": True}
    assert service.deleted_bindings == [(user.id, "generic_oidc")]
