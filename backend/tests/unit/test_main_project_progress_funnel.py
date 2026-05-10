from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.v1.main_projects import get_main_project_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.main_projects import MainProject
from app.models.phases import PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole
from app.services.main_projects import (
    InMemoryMainProjectRepository,
    MainProjectService,
    ProjectProgressFunnel,
    ProjectProgressFunnelItem,
    ProjectProgressFunnelSubProject,
)
from tests.factories import MainProjectFactory, PhaseFactory, SubProjectFactory, UserFactory


@pytest.mark.asyncio
async def test_progress_funnel_groups_active_phase_and_drill_sub_projects() -> None:
    actor = cast(User, UserFactory(role=UserRole.dept_manager))
    project = cast(MainProject, MainProjectFactory())
    procurement_sub_project = cast(
        SubProject,
        SubProjectFactory(
            main_project_id=project.id,
            name="采购实施",
            project_no="Z-2026-0001-ZX-001",
        ),
    )
    initiation_sub_project = cast(
        SubProject,
        SubProjectFactory(
            main_project_id=project.id,
            name="立项准备",
            project_no="Z-2026-0001-ZX-002",
        ),
    )
    repository = InMemoryMainProjectRepository(
        [project],
        sub_projects=[procurement_sub_project, initiation_sub_project],
        phases=[
            PhaseFactory(
                sub_project_id=procurement_sub_project.id,
                phase_no=1,
                code="initiation",
                name="立项",
                status=PhaseStatus.completed,
            ),
            PhaseFactory(
                sub_project_id=procurement_sub_project.id,
                phase_no=2,
                code="procurement",
                name="采购",
                status=PhaseStatus.in_progress,
            ),
            PhaseFactory(
                sub_project_id=initiation_sub_project.id,
                phase_no=1,
                code="initiation",
                name="立项",
                status=PhaseStatus.in_progress,
            ),
            PhaseFactory(
                sub_project_id=initiation_sub_project.id,
                phase_no=2,
                code="procurement",
                name="采购",
                status=PhaseStatus.waiting,
            ),
        ],
    )
    service = MainProjectService(repository=repository)

    funnel = await service.get_progress_funnel(actor=actor, project_id=project.id)

    assert funnel.main_project_id == project.id
    assert funnel.total_sub_projects == 2
    assert [item.phase_no for item in funnel.items] == [1, 2, 3, 4, 5, 6]
    phase_one = funnel.items[0]
    phase_two = funnel.items[1]
    assert phase_one.sub_project_count == 1
    assert phase_one.sub_projects[0].name == "立项准备"
    assert phase_two.sub_project_count == 1
    assert phase_two.sub_projects[0].name == "采购实施"
    assert phase_two.sub_projects[0].phase_status == PhaseStatus.in_progress


@pytest.mark.asyncio
async def test_progress_funnel_requires_project_view_permission() -> None:
    actor = cast(User, UserFactory(role=UserRole.proj_member))
    project = cast(MainProject, MainProjectFactory())
    service = MainProjectService(repository=InMemoryMainProjectRepository([project]))

    with pytest.raises(PermissionDeniedError):
        await service.get_progress_funnel(actor=actor, project_id=project.id)


def test_progress_funnel_endpoint_returns_standard_payload() -> None:
    actor = cast(User, UserFactory(role=UserRole.dept_manager))
    project = cast(MainProject, MainProjectFactory())
    sub_project = cast(
        SubProject,
        SubProjectFactory(
            main_project_id=project.id,
            name="立项准备",
            project_no="Z-2026-0001-ZX-001",
        ),
    )

    class FakeMainProjectService:
        async def get_progress_funnel(
            self,
            *,
            actor: object,
            project_id: UUID,
        ) -> ProjectProgressFunnel:
            assert project_id == project.id
            return ProjectProgressFunnel(
                main_project_id=project.id,
                total_sub_projects=1,
                items=[
                    ProjectProgressFunnelItem(
                        phase_no=1,
                        code="initiation",
                        name="立项",
                        sub_project_count=1,
                        sub_projects=[
                            ProjectProgressFunnelSubProject(
                                id=sub_project.id,
                                project_no=sub_project.project_no,
                                name=sub_project.name,
                                status=SubProjectStatus.in_progress,
                                phase_status=PhaseStatus.in_progress,
                            ),
                        ],
                    ),
                ],
            )

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return actor

    async def fake_main_project_service() -> FakeMainProjectService:
        return FakeMainProjectService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_main_project_service] = fake_main_project_service

    response = TestClient(app).get(f"/api/v1/main-projects/{project.id}/progress-funnel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["main_project_id"] == str(project.id)
    assert payload["data"]["items"][0]["phase_no"] == 1
    assert payload["data"]["items"][0]["sub_project_count"] == 1
    assert payload["data"]["items"][0]["sub_projects"][0]["name"] == "立项准备"
