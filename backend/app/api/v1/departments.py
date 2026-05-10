from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.schemas.departments import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.departments import DepartmentService, SqlAlchemyDepartmentRepository

router = APIRouter(prefix="/departments", tags=["departments"])


async def get_department_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DepartmentService:
    return DepartmentService(repository=SqlAlchemyDepartmentRepository(session))


def serialize_department(department: object) -> dict[str, object]:
    return DepartmentRead.model_validate(department).model_dump(mode="json")


@router.get("")
async def list_departments(
    service: Annotated[DepartmentService, Depends(get_department_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _ = current_user
    departments = await service.list_departments()
    return success_response([serialize_department(department) for department in departments])


@router.post("")
async def create_department(
    payload: DepartmentCreate,
    service: Annotated[DepartmentService, Depends(get_department_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    department = await service.create_department(actor=current_user, payload=payload)
    return success_response(serialize_department(department))


@router.put("/{department_id}")
async def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    service: Annotated[DepartmentService, Depends(get_department_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    department = await service.update_department(
        actor=current_user,
        department_id=department_id,
        payload=payload,
    )
    return success_response(serialize_department(department))


@router.delete("/{department_id}")
async def delete_department(
    department_id: UUID,
    service: Annotated[DepartmentService, Depends(get_department_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    department = await service.delete_department(actor=current_user, department_id=department_id)
    return success_response(serialize_department(department))
