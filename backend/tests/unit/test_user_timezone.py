from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.security import hash_password
from app.models.users import User, UserRole, UserStatus
from app.schemas.users import UserCreate, UserUpdate
from app.services.auth import InMemoryAuthTokenStore
from app.services.users import InMemoryProjectAssignmentReader, InMemoryUserRepository, UserService


def make_user(*, role: UserRole = UserRole.admin, username: str = "admin") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash=hash_password("StrongPass1!"),
        role=role,
        dept_id=None,
        status=UserStatus.active,
        sso_required=False,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_service(*users: User) -> UserService:
    return UserService(
        repository=InMemoryUserRepository(list(users)),
        token_store=InMemoryAuthTokenStore(),
        project_reader=InMemoryProjectAssignmentReader(),
        token_revoke_ttl_seconds=3600,
    )


@pytest.mark.asyncio
async def test_create_user_defaults_timezone_to_asia_shanghai() -> None:
    admin = make_user()
    service = make_service(admin)

    created = await service.create_user(
        actor=admin,
        payload=UserCreate(
            username="member",
            password="StrongPass1!",
            role=UserRole.proj_member,
        ),
    )

    assert created.timezone == "Asia/Shanghai"


@pytest.mark.asyncio
async def test_create_user_accepts_valid_iana_timezone() -> None:
    admin = make_user()
    service = make_service(admin)

    created = await service.create_user(
        actor=admin,
        payload=UserCreate(
            username="ny-member",
            password="StrongPass1!",
            role=UserRole.proj_member,
            timezone="America/New_York",
        ),
    )

    assert created.timezone == "America/New_York"


def test_user_payload_rejects_invalid_timezone() -> None:
    with pytest.raises(ValidationError):
        UserUpdate(timezone="Mars/Base")


@pytest.mark.asyncio
async def test_user_can_update_own_timezone() -> None:
    member = make_user(role=UserRole.proj_member, username="member")
    service = make_service(member)

    updated = await service.update_user(
        actor=member,
        user_id=member.id,
        payload=UserUpdate(timezone="Europe/Berlin"),
    )

    assert updated.timezone == "Europe/Berlin"
