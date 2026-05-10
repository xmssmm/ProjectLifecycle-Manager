from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from sqlalchemy import Table, UniqueConstraint

from app.core.exceptions import AuthenticationError
from app.models.base import Base
from app.models.oauth import OAuthBinding
from app.services.oauth import (
    InMemoryOAuthBindingRepository,
    InMemoryOAuthStateStore,
    OAuthHttpClient,
    OAuthProviderConfig,
    OAuthService,
)


def make_provider() -> OAuthProviderConfig:
    return OAuthProviderConfig(
        provider="generic_oidc",
        client_id="client-id",
        client_secret="client-secret",
        authorize_url="https://sso.example.local/oauth/authorize",
        token_url="https://sso.example.local/oauth/token",
        userinfo_url="https://sso.example.local/oauth/userinfo",
        redirect_uri="https://app.example.local/api/v1/oauth/generic_oidc/callback",
        scope="openid email profile",
    )


class FakeOAuthHttpClient(OAuthHttpClient):
    def __init__(
        self,
        *,
        token_response: Mapping[str, object] | None = None,
        userinfo_response: Mapping[str, object] | None = None,
    ) -> None:
        self.token_response = dict(token_response or {})
        self.userinfo_response = dict(userinfo_response or {})
        self.posted_form: dict[str, object] | None = None
        self.userinfo_headers: dict[str, str] | None = None

    async def post_form(
        self,
        url: str,
        *,
        data: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        _ = url, headers
        self.posted_form = dict(data)
        return self.token_response

    async def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        _ = url
        self.userinfo_headers = dict(headers or {})
        return self.userinfo_response


def test_oauth_binding_table_has_required_columns_and_constraints() -> None:
    assert "oauth_bindings" in Base.metadata.tables

    table = OAuthBinding.__table__
    assert isinstance(table, Table)
    assert {
        "id",
        "user_id",
        "provider",
        "external_id",
        "email",
        "access_token_ciphertext",
        "refresh_token_ciphertext",
        "expires_at",
        "created_at",
        "updated_at",
    }.issubset(set(table.c.keys()))

    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("provider", "external_id") in unique_columns
    assert ("user_id", "provider") in unique_columns


@pytest.mark.asyncio
async def test_start_login_builds_authorization_url_and_stores_state() -> None:
    provider = make_provider()
    state_store = InMemoryOAuthStateStore()
    service = OAuthService(
        providers={provider.provider: provider},
        state_store=state_store,
        http_client=FakeOAuthHttpClient(),
        binding_repository=InMemoryOAuthBindingRepository(),
    )

    started = await service.start_login(provider.provider)
    parsed = urlparse(started.authorization_url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "sso.example.local"
    assert parsed.path == "/oauth/authorize"
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [provider.redirect_uri]
    assert query["scope"] == [provider.scope]
    assert query["state"] == [started.state]
    assert await state_store.peek_state(started.state) is not None


@pytest.mark.asyncio
async def test_handle_callback_rejects_missing_or_reused_state() -> None:
    provider = make_provider()
    service = OAuthService(
        providers={provider.provider: provider},
        state_store=InMemoryOAuthStateStore(),
        http_client=FakeOAuthHttpClient(),
        binding_repository=InMemoryOAuthBindingRepository(),
    )

    with pytest.raises(AuthenticationError, match="Invalid OAuth state"):
        await service.handle_callback(
            provider=provider.provider,
            code="code",
            state="missing",
        )


@pytest.mark.asyncio
async def test_handle_callback_exchanges_code_loads_userinfo_and_consumes_state() -> None:
    provider = make_provider()
    state_store = InMemoryOAuthStateStore()
    http_client = FakeOAuthHttpClient(
        token_response={
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
        userinfo_response={
            "sub": "external-user-1",
            "email": "member@example.local",
            "email_verified": True,
            "name": "Member",
        },
    )
    service = OAuthService(
        providers={provider.provider: provider},
        state_store=state_store,
        http_client=http_client,
        binding_repository=InMemoryOAuthBindingRepository(),
        now_provider=lambda: datetime(2026, 5, 10, 1, 0, tzinfo=UTC),
    )
    started = await service.start_login(provider.provider)

    identity = await service.handle_callback(
        provider=provider.provider,
        code="auth-code",
        state=started.state,
    )

    assert http_client.posted_form == {
        "grant_type": "authorization_code",
        "code": "auth-code",
        "redirect_uri": provider.redirect_uri,
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
    }
    assert http_client.userinfo_headers == {"Authorization": "Bearer access-token"}
    assert identity.provider == "generic_oidc"
    assert identity.external_id == "external-user-1"
    assert identity.email == "member@example.local"
    assert identity.email_verified is True
    assert identity.display_name == "Member"
    assert identity.bound_user_id is None
    assert identity.access_token_ciphertext == "access-token"
    assert identity.refresh_token_ciphertext == "refresh-token"
    assert identity.expires_at == datetime(2026, 5, 10, 2, 0, tzinfo=UTC)

    with pytest.raises(AuthenticationError, match="Invalid OAuth state"):
        await service.handle_callback(
            provider=provider.provider,
            code="auth-code",
            state=started.state,
        )


@pytest.mark.asyncio
async def test_handle_callback_rejects_token_or_userinfo_without_required_fields() -> None:
    provider = make_provider()
    state_store = InMemoryOAuthStateStore()
    service = OAuthService(
        providers={provider.provider: provider},
        state_store=state_store,
        http_client=FakeOAuthHttpClient(
            token_response={"token_type": "Bearer"},
            userinfo_response={},
        ),
        binding_repository=InMemoryOAuthBindingRepository(),
    )
    started = await service.start_login(provider.provider)

    with pytest.raises(AuthenticationError, match="OAuth token response is invalid"):
        await service.handle_callback(
            provider=provider.provider,
            code="auth-code",
            state=started.state,
        )

    state_store = InMemoryOAuthStateStore()
    service = OAuthService(
        providers={provider.provider: provider},
        state_store=state_store,
        http_client=FakeOAuthHttpClient(
            token_response={"access_token": "access-token"},
            userinfo_response={"email": "member@example.local"},
        ),
        binding_repository=InMemoryOAuthBindingRepository(),
    )
    started = await service.start_login(provider.provider)

    with pytest.raises(AuthenticationError, match="OAuth userinfo response is invalid"):
        await service.handle_callback(
            provider=provider.provider,
            code="auth-code",
            state=started.state,
        )


@pytest.mark.asyncio
async def test_handle_callback_resolves_existing_binding_user_id() -> None:
    provider = make_provider()
    bound_user_id = uuid4()
    repository = InMemoryOAuthBindingRepository(
        [
            OAuthBinding(
                user_id=bound_user_id,
                provider=provider.provider,
                external_id="external-user-1",
                email="member@example.local",
                access_token_ciphertext="old-token",
                refresh_token_ciphertext=None,
                expires_at=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ],
    )
    state_store = InMemoryOAuthStateStore()
    service = OAuthService(
        providers={provider.provider: provider},
        state_store=state_store,
        http_client=FakeOAuthHttpClient(
            token_response={"access_token": "access-token"},
            userinfo_response={"sub": "external-user-1"},
        ),
        binding_repository=repository,
    )
    started = await service.start_login(provider.provider)

    identity = await service.handle_callback(
        provider=provider.provider,
        code="auth-code",
        state=started.state,
    )

    assert identity.bound_user_id == bound_user_id
