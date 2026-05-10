from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, false
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.departments import Department


class UserRole(enum.StrEnum):
    admin = "admin"
    dept_manager = "dept_manager"
    finance_manager = "finance_manager"
    proj_leader = "proj_leader"
    proj_member = "proj_member"


class UserStatus(enum.StrEnum):
    active = "active"
    disabled = "disabled"
    password_reset_required = "password_reset_required"


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_type]


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("sso_required", False)
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise TypeError(f"{key!r} is an invalid keyword argument for User")
            setattr(self, key, value)

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=enum_values),
        nullable=False,
    )
    dept_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=enum_values),
        nullable=False,
        default=UserStatus.active,
        server_default=UserStatus.active.value,
    )
    sso_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    department: Mapped[Department | None] = relationship(back_populates="users")
