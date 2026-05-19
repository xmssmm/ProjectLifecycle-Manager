from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.permissions import get_role_permission_service
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.schemas.role_permissions import RolePermissionUpdate
from app.services.role_permissions import RolePermissionService

router = APIRouter(prefix="/role-permissions", tags=["role-permissions"])


@router.get("")
async def list_role_permissions(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RolePermissionService, Depends(get_role_permission_service)],
) -> dict[str, object]:
    matrix = await service.list_matrix(actor=current_user)
    return success_response(matrix.model_dump(mode="json"))


@router.put("/{role}")
async def update_role_permissions(
    role: UserRole,
    payload: RolePermissionUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RolePermissionService, Depends(get_role_permission_service)],
) -> dict[str, object]:
    updated = await service.update_role_permissions(
        actor=current_user,
        role=role,
        permission_codes=payload.permission_codes,
    )
    return success_response(updated.model_dump(mode="json"))
