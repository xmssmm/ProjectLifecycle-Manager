from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    InFlightProjectsBlockDisableError,
    PasswordStrengthError,
    PermissionDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.core.security import hash_password, validate_password_strength, verify_password
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.users import PasswordChangeRequest, PasswordResetRequest, UserCreate, UserUpdate
from app.services.auth import AuthTokenStore


class UserRepository(Protocol):
    async def list_users(
        self,
        *,
        role: UserRole | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        ...

    async def get_by_id(self, user_id: UUID) -> User | None:
        ...

    async def get_by_username(self, username: str) -> User | None:
        ...

    async def get_by_email(self, email: str) -> User | None:
        ...

    def add(self, user: User) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, user: User) -> None:
        ...


class ProjectAssignmentReader(Protocol):
    async def count_active_sub_projects_for_leader(self, user_id: UUID) -> int:
        ...


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_users(
        self,
        *,
        role: UserRole | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        conditions = []
        if role is not None:
            conditions.append(User.role == role)

        total = await self._session.scalar(
            select(func.count()).select_from(User).where(*conditions),
        )
        statement = (
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        users = list((await self._session.scalars(statement)).all())
        return users, int(total or 0)

    async def get_by_id(self, user_id: UUID) -> User | None:
        user = await self._session.get(User, user_id)
        return user if isinstance(user, User) else None

    async def get_by_username(self, username: str) -> User | None:
        return cast(
            User | None,
            await self._session.scalar(select(User).where(User.username == username)),
        )

    async def get_by_email(self, email: str) -> User | None:
        return cast(
            User | None,
            await self._session.scalar(select(User).where(User.email == email)),
        )

    def add(self, user: User) -> None:
        self._session.add(user)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, user: User) -> None:
        await self._session.refresh(user)


class SqlAlchemyProjectAssignmentReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_active_sub_projects_for_leader(self, user_id: UUID) -> int:
        value = await self._session.scalar(
            select(func.count()).select_from(SubProject).where(
                SubProject.manager_id == user_id,
                SubProject.status.in_(
                    [
                        SubProjectStatus.not_started,
                        SubProjectStatus.in_progress,
                        SubProjectStatus.completed,
                    ],
                ),
            ),
        )
        return int(value or 0)


class InMemoryUserRepository:
    def __init__(self, users: Sequence[User] | None = None) -> None:
        self.users = list(users or [])

    async def list_users(
        self,
        *,
        role: UserRole | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        filtered = [user for user in self.users if role is None or user.role == role]
        start = (page - 1) * page_size
        return filtered[start : start + page_size], len(filtered)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((user for user in self.users if user.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users if user.email == email), None)

    def add(self, user: User) -> None:
        self.users.append(user)

    async def commit(self) -> None:
        return None

    async def refresh(self, user: User) -> None:
        return None


class InMemoryProjectAssignmentReader:
    def __init__(self, active_counts: dict[UUID, int] | None = None) -> None:
        self._active_counts = active_counts or {}

    async def count_active_sub_projects_for_leader(self, user_id: UUID) -> int:
        return self._active_counts.get(user_id, 0)


class NoopProjectAssignmentReader:
    async def count_active_sub_projects_for_leader(self, user_id: UUID) -> int:
        _ = user_id
        return 0


class UserService:
    def __init__(
        self,
        *,
        repository: UserRepository,
        token_store: AuthTokenStore,
        project_reader: ProjectAssignmentReader,
        token_revoke_ttl_seconds: int,
    ) -> None:
        self._repository = repository
        self._token_store = token_store
        self._project_reader = project_reader
        self._token_revoke_ttl_seconds = token_revoke_ttl_seconds

    async def list_users(
        self,
        *,
        actor: User,
        role: UserRole | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        self._ensure_admin(actor)
        return await self._repository.list_users(role=role, page=page, page_size=page_size)

    async def create_user(self, *, actor: User, payload: UserCreate) -> User:
        self._ensure_admin(actor)
        self._validate_password(payload.password)
        await self._ensure_unique_username(payload.username)
        if payload.email is not None:
            await self._ensure_unique_email(payload.email)

        now = datetime.now(UTC)
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            dept_id=payload.dept_id,
            status=UserStatus.active,
            password_changed_at=now,
            last_login_at=None,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(user)
        await self._repository.commit()
        await self._repository.refresh(user)
        return user

    async def get_user(self, *, actor: User, user_id: UUID) -> User:
        user = await self._get_existing_user(user_id)
        if actor.role != UserRole.admin and actor.id != user.id:
            raise PermissionDeniedError()
        return user

    async def update_user(self, *, actor: User, user_id: UUID, payload: UserUpdate) -> User:
        user = await self._get_existing_user(user_id)
        is_admin = actor.role == UserRole.admin
        if not is_admin and actor.id != user.id:
            raise PermissionDeniedError()

        fields = payload.model_fields_set
        if not is_admin and ({"username", "role", "dept_id"} & fields):
            raise PermissionDeniedError()

        if payload.username is not None and payload.username != user.username:
            await self._ensure_unique_username(payload.username, excluding_user_id=user.id)
            user.username = payload.username
        if "email" in fields and payload.email != user.email:
            if payload.email is not None:
                await self._ensure_unique_email(payload.email, excluding_user_id=user.id)
            user.email = payload.email
        if is_admin and payload.role is not None:
            user.role = payload.role
        if is_admin and "dept_id" in fields:
            user.dept_id = payload.dept_id

        await self._repository.commit()
        await self._repository.refresh(user)
        return user

    async def disable_user(self, *, actor: User, user_id: UUID) -> User:
        self._ensure_admin(actor)
        user = await self._get_existing_user(user_id)
        if user.role == UserRole.proj_leader:
            in_flight_count = await self._project_reader.count_active_sub_projects_for_leader(
                user.id,
            )
            if in_flight_count > 0:
                raise InFlightProjectsBlockDisableError(in_flight_count)

        user.status = UserStatus.disabled
        await self._revoke_user_tokens(user.id)
        await self._repository.commit()
        await self._repository.refresh(user)
        return user

    async def reset_password(
        self,
        *,
        actor: User,
        user_id: UUID,
        payload: PasswordResetRequest,
    ) -> User:
        self._ensure_admin(actor)
        user = await self._get_existing_user(user_id)
        self._validate_password(payload.new_password)
        user.password_hash = hash_password(payload.new_password)
        user.status = UserStatus.password_reset_required
        user.password_changed_at = datetime.now(UTC)
        await self._revoke_user_tokens(user.id)
        await self._repository.commit()
        await self._repository.refresh(user)
        return user

    async def change_own_password(self, *, actor: User, payload: PasswordChangeRequest) -> User:
        if not verify_password(payload.old_password, actor.password_hash):
            raise AuthenticationError("旧密码不正确")
        self._validate_password(payload.new_password)
        actor.password_hash = hash_password(payload.new_password)
        actor.status = UserStatus.active
        actor.password_changed_at = datetime.now(UTC)
        await self._revoke_user_tokens(actor.id)
        await self._repository.commit()
        await self._repository.refresh(actor)
        return actor

    async def _get_existing_user(self, user_id: UUID) -> User:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("用户不存在")
        return user

    async def _ensure_unique_username(
        self,
        username: str,
        *,
        excluding_user_id: UUID | None = None,
    ) -> None:
        existing = await self._repository.get_by_username(username)
        if existing is not None and existing.id != excluding_user_id:
            raise ResourceConflictError("用户名已存在", data={"field": "username"})

    async def _ensure_unique_email(
        self,
        email: str,
        *,
        excluding_user_id: UUID | None = None,
    ) -> None:
        existing = await self._repository.get_by_email(email)
        if existing is not None and existing.id != excluding_user_id:
            raise ResourceConflictError("邮箱已存在", data={"field": "email"})

    async def _revoke_user_tokens(self, user_id: UUID) -> None:
        await self._token_store.revoke_user_tokens(str(user_id), self._token_revoke_ttl_seconds)

    @staticmethod
    def _ensure_admin(actor: User) -> None:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()

    @staticmethod
    def _validate_password(password: str) -> None:
        try:
            validate_password_strength(password)
        except ValueError as exc:
            raise PasswordStrengthError(str(exc)) from exc
