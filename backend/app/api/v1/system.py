from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.services.system_health import SqlAlchemyRoleHealthReader, SystemHealthService

router = APIRouter(prefix="/system", tags=["system"])


async def get_system_health_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SystemHealthService:
    return SystemHealthService(role_reader=SqlAlchemyRoleHealthReader(session))


@router.get("/health-warnings")
async def list_health_warnings(
    service: Annotated[SystemHealthService, Depends(get_system_health_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    _ = current_user
    warnings = await service.collect_warnings()
    return success_response(warnings)
