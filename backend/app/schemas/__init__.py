"""Pydantic schemas package."""
from app.schemas.departments import DepartmentRead
from app.schemas.users import UserRead

__all__ = ["DepartmentRead", "UserRead"]
