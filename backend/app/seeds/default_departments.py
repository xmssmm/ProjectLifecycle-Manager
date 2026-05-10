from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.departments import Department


@dataclass(frozen=True)
class DepartmentSeed:
    code: str
    name: str


DEFAULT_DEPARTMENTS = (
    DepartmentSeed(code="general", name="\u7efc\u5408\u90e8"),
    DepartmentSeed(code="finance", name="\u8d22\u52a1\u90e8"),
    DepartmentSeed(code="business", name="\u4e1a\u52a1\u90e8"),
)


async def seed_default_departments(session: AsyncSession) -> int:
    codes = [department.code for department in DEFAULT_DEPARTMENTS]
    existing_codes = set(
        await session.scalars(select(Department.code).where(Department.code.in_(codes))),
    )
    inserted = 0
    for department in DEFAULT_DEPARTMENTS:
        if department.code in existing_codes:
            continue
        session.add(Department(code=department.code, name=department.name))
        inserted += 1
    return inserted
