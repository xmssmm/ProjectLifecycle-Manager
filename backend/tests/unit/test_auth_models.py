from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum as SqlEnum

from app.models.base import Base
from app.models.departments import Department
from app.models.users import User, UserRole, UserStatus
from app.schemas.departments import DepartmentRead
from app.schemas.users import UserRead


def test_user_role_enum_is_the_requirements_closed_set() -> None:
    assert [role.value for role in UserRole] == [
        "admin",
        "dept_manager",
        "finance_manager",
        "proj_leader",
        "proj_member",
    ]
    role_type = User.__table__.c.role.type
    assert isinstance(role_type, SqlEnum)
    assert role_type.enums == [role.value for role in UserRole]


def test_user_and_department_tables_have_required_columns() -> None:
    assert "users" in Base.metadata.tables
    assert "departments" in Base.metadata.tables

    user_columns = set(User.__table__.c.keys())
    department_columns = set(Department.__table__.c.keys())

    assert {
        "id",
        "username",
        "password_hash",
        "role",
        "dept_id",
        "status",
        "password_changed_at",
        "last_login_at",
    }.issubset(user_columns)
    assert {"id", "name", "code", "created_at", "updated_at"}.issubset(department_columns)


def test_user_and_department_schemas_serialize_from_models() -> None:
    department_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)
    department = Department(
        id=department_id,
        code="general",
        name="General Department",
        created_at=now,
        updated_at=now,
    )
    user = User(
        id=user_id,
        username="admin",
        email="admin@example.local",
        password_hash="hashed",
        role=UserRole.admin,
        dept_id=department_id,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )

    department_payload = DepartmentRead.model_validate(department).model_dump()
    user_payload = UserRead.model_validate(user).model_dump()

    assert department_payload["id"] == department_id
    assert department_payload["name"] == "General Department"
    assert user_payload["id"] == user_id
    assert user_payload["role"] == UserRole.admin
    assert user_payload["dept_id"] == department_id


def test_user_id_schema_fields_are_uuid_typed() -> None:
    assert UserRead.model_fields["id"].annotation is UUID
    assert UserRead.model_fields["dept_id"].annotation == UUID | None
