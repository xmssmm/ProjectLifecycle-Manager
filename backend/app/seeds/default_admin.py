from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.users import User, UserRole, UserStatus


@dataclass(frozen=True)
class DefaultAdminCredentials:
    username: str
    password: str


def get_default_admin_credentials() -> DefaultAdminCredentials:
    username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin").strip()
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin123!").strip()
    if not username:
        raise ValueError("DEFAULT_ADMIN_USERNAME must not be blank")
    if not password:
        raise ValueError("DEFAULT_ADMIN_PASSWORD must not be blank")
    return DefaultAdminCredentials(username=username, password=password)


async def seed_default_admin(session: AsyncSession) -> int:
    credentials = get_default_admin_credentials()
    existing = await session.scalar(select(User.id).where(User.username == credentials.username))
    if existing is not None:
        return 0

    now = datetime.now(UTC)
    session.add(
        User(
            username=credentials.username,
            email=(os.getenv("DEFAULT_ADMIN_EMAIL") or "").strip() or None,
            password_hash=hash_password(credentials.password),
            role=UserRole.admin,
            dept_id=None,
            status=UserStatus.active,
            password_changed_at=now,
            last_login_at=None,
        ),
    )
    return 1
