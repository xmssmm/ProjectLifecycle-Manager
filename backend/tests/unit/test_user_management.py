from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.users import get_user_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.core.security import hash_password, verify_password
from app.main import create_app
from app.models.users import User, UserRole, UserStatus
from app.schemas.users import PasswordChangeRequest, PasswordResetRequest, UserCreate
from app.services.auth import InMemoryAuthTokenStore
from app.services.users import (
    InMemoryProjectAssignmentReader,
    InMemoryUserRepository,
    UserService,
)


def make_user(
    *,
    role: UserRole = UserRole.admin,
    status: UserStatus = UserStatus.active,
    username: str = "admin",
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash=hash_password("StrongPass1!"),
        role=role,
        dept_id=None,
        status=status,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


@dataclass
class RecordingTokenStore(InMemoryAuthTokenStore):
    revoked_user_ids: list[str] = field(default_factory=list)

    async def revoke_user_tokens(self, user_id: str, ttl_seconds: int) -> None:
        self.revoked_user_ids.append(user_id)
        await super().revoke_user_tokens(user_id, ttl_seconds)


def make_service(*users: User) -> tuple[UserService, InMemoryUserRepository, RecordingTokenStore]:
    token_store = RecordingTokenStore()
    repository = InMemoryUserRepository(list(users))
    service = UserService(
        repository=repository,
        token_store=token_store,
        project_reader=InMemoryProjectAssignmentReader(),
        token_revoke_ttl_seconds=3600,
    )
    return service, repository, token_store


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_rejects_weak_password() -> None:
    admin = make_user()
    service, repository, _token_store = make_service(admin)

    with pytest.raises(BusinessException) as weak_password:
        await service.create_user(
            actor=admin,
            payload=UserCreate(
                username="member",
                password="weak",
                role=UserRole.proj_member,
            ),
        )
    assert weak_password.value.code == 2004

    created = await service.create_user(
        actor=admin,
        payload=UserCreate(
            username="member",
            email="member@example.local",
            password="StrongPass1!",
            role=UserRole.proj_member,
        ),
    )

    assert created in repository.users
    assert created.password_hash != "StrongPass1!"
    assert verify_password("StrongPass1!", created.password_hash)
    assert created.status == UserStatus.active


@pytest.mark.asyncio
async def test_disable_proj_leader_with_active_sub_projects_is_rejected() -> None:
    admin = make_user()
    leader = make_user(role=UserRole.proj_leader, username="leader")
    token_store = RecordingTokenStore()
    service = UserService(
        repository=InMemoryUserRepository([admin, leader]),
        token_store=token_store,
        project_reader=InMemoryProjectAssignmentReader({leader.id: 2}),
        token_revoke_ttl_seconds=3600,
    )

    with pytest.raises(BusinessException) as blocked:
        await service.disable_user(actor=admin, user_id=leader.id)

    assert blocked.value.code == 3010
    assert blocked.value.data == {"in_flight_count": 2, "sample_projects": []}
    assert leader.status == UserStatus.active
    assert token_store.revoked_user_ids == []


@pytest.mark.asyncio
async def test_disable_user_and_change_password_revoke_existing_tokens() -> None:
    admin = make_user()
    member = make_user(role=UserRole.proj_member, username="member")
    service, _repository, token_store = make_service(admin, member)

    disabled = await service.disable_user(actor=admin, user_id=member.id)
    assert disabled.status == UserStatus.disabled
    assert str(member.id) in token_store.revoked_user_ids

    admin_old_hash = admin.password_hash
    changed = await service.change_own_password(
        actor=admin,
        payload=PasswordChangeRequest(
            old_password="StrongPass1!",
            new_password="NewStrong1!",
        ),
    )

    assert changed.password_hash != admin_old_hash
    assert verify_password("NewStrong1!", changed.password_hash)
    assert str(admin.id) in token_store.revoked_user_ids


@pytest.mark.asyncio
async def test_reset_password_marks_user_for_required_change_and_revokes_tokens() -> None:
    admin = make_user()
    member = make_user(role=UserRole.proj_member, username="member")
    service, _repository, token_store = make_service(admin, member)

    reset = await service.reset_password(
        actor=admin,
        user_id=member.id,
        payload=PasswordResetRequest(new_password="ResetPass1!"),
    )

    assert reset.status == UserStatus.password_reset_required
    assert verify_password("ResetPass1!", reset.password_hash)
    assert str(member.id) in token_store.revoked_user_ids


def test_user_list_endpoint_requires_admin_role() -> None:
    member = make_user(role=UserRole.proj_member, username="member")

    class FakeUserService:
        async def list_users(
            self,
            *,
            role: UserRole | None = None,
            page: int = 1,
            page_size: int = 20,
        ) -> tuple[list[User], int]:
            _ = role, page, page_size
            return [], 0

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return member

    async def fake_user_service() -> FakeUserService:
        return FakeUserService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_user_service] = fake_user_service
    client = TestClient(app)

    response = client.get("/api/v1/users")

    assert response.status_code == 403
    assert response.json()["code"] == PermissionDeniedError().code


def test_user_endpoints_return_standard_success_payloads() -> None:
    admin = make_user()
    created_user = make_user(role=UserRole.proj_member, username="created")

    class FakeUserService:
        async def list_users(
            self,
            *,
            actor: User,
            role: UserRole | None = None,
            page: int = 1,
            page_size: int = 20,
        ) -> tuple[list[User], int]:
            assert actor == admin
            assert role == UserRole.proj_member
            assert page == 1
            assert page_size == 20
            return [created_user], 1

        async def create_user(self, *, actor: User, payload: UserCreate) -> User:
            assert actor == admin
            assert payload.username == "created"
            return created_user

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return admin

    async def fake_user_service() -> FakeUserService:
        return FakeUserService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_user_service] = fake_user_service
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/users",
        json={
            "username": "created",
            "password": "StrongPass1!",
            "role": UserRole.proj_member.value,
        },
    )
    list_response = client.get("/api/v1/users?role=proj_member")

    assert create_response.status_code == 200
    assert create_response.json()["data"]["username"] == "created"
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1
    assert list_response.json()["data"]["items"][0]["role"] == UserRole.proj_member.value
