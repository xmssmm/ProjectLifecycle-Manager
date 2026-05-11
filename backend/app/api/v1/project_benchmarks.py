from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.users import User
from app.services.project_benchmarks import (
    ProjectBenchmarkService,
    SqlAlchemyProjectBenchmarkRepository,
)

router = APIRouter(prefix="/project-benchmarks", tags=["project-benchmarks"])


async def get_project_benchmark_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectBenchmarkService:
    return ProjectBenchmarkService(repository=SqlAlchemyProjectBenchmarkRepository(session))


@router.get("/{project_id}")
async def analyze_project_benchmark(
    project_id: UUID,
    service: Annotated[ProjectBenchmarkService, Depends(get_project_benchmark_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    result = await service.analyze_project(actor=current_user, project_id=project_id)
    return success_response(result.to_dict())
