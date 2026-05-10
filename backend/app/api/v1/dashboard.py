from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.services.dashboard import (
    DashboardService,
    RedisDashboardCache,
    SqlAlchemyDashboardRepository,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def get_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DashboardService:
    return DashboardService(
        repository=SqlAlchemyDashboardRepository(session),
        cache=RedisDashboardCache(settings.redis_url),
    )


@router.get("/{role_scope}")
async def get_dashboard(
    role_scope: UserRole,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    dashboard = await service.get_dashboard(actor=current_user, role_scope=role_scope)
    return success_response(dashboard)
