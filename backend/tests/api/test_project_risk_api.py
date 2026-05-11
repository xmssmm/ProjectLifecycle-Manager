from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.project_risk import get_project_risk_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole
from app.services.project_benchmarks import (
    BenchmarkProjectSnapshot,
    InMemoryProjectBenchmarkRepository,
)
from app.services.project_risk import ProjectRiskService
from tests.factories import UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


def test_project_risk_api_returns_score_and_summary() -> None:
    dept_id = uuid4()
    actor = cast(User, UserFactory(role=UserRole.admin, dept_id=dept_id))
    target = BenchmarkProjectSnapshot(
        id=uuid4(),
        category_id=None,
        closed_at=None,
        created_at=NOW - timedelta(days=30),
        creator_id=None,
        dept_id=dept_id,
        expected_finish_date=date(2026, 5, 1),
        participant_user_ids=frozenset(),
        phase_durations_days=(3,),
        project_no="Z-2026-0001",
        project_type_id=None,
        spent_amount=Decimal("180.00"),
        tag_ids=(),
        task_count=10,
        overdue_task_count=8,
        total_budget=Decimal("100.00"),
        updated_at=NOW,
    )
    service = ProjectRiskService(
        repository=InMemoryProjectBenchmarkRepository([target]),
        now_provider=lambda: NOW,
    )

    response = build_client(actor, service).get(f"/api/v1/project-risk/{target.id}")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["project_id"] == str(target.id)
    assert payload["score"] > 70
    assert payload["summary"]["source"] == "rules"


def build_client(user: User, service: ProjectRiskService) -> TestClient:
    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> ProjectRiskService:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_project_risk_service] = fake_service
    return TestClient(app)
