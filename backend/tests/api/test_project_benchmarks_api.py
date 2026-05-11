from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.project_benchmarks import get_project_benchmark_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole
from app.services.project_benchmarks import (
    BenchmarkProjectSnapshot,
    InMemoryProjectBenchmarkRepository,
    ProjectBenchmarkService,
)
from tests.factories import UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


def test_project_benchmark_api_returns_peer_statistics() -> None:
    dept_id = uuid4()
    type_id = uuid4()
    admin = cast(User, UserFactory(role=UserRole.admin, dept_id=dept_id))
    target = make_snapshot(dept_id=dept_id, project_type_id=type_id, cycle_days=15)
    samples = [
        make_snapshot(dept_id=dept_id, project_type_id=type_id, cycle_days=days)
        for days in [10, 20, 30, 40, 50]
    ]
    service = ProjectBenchmarkService(
        repository=InMemoryProjectBenchmarkRepository([target, *samples]),
        min_sample_size=5,
        now_provider=lambda: NOW,
    )

    response = build_client(admin, service).get(f"/api/v1/project-benchmarks/{target.id}")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["project_id"] == str(target.id)
    assert payload["status"] == "ready"
    assert payload["sample_count"] == 5
    cycle_metric = next(item for item in payload["metrics"] if item["key"] == "cycle_days")
    assert cycle_metric["p50"] == 30


def build_client(user: User, service: ProjectBenchmarkService) -> TestClient:
    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> ProjectBenchmarkService:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_project_benchmark_service] = fake_service
    return TestClient(app)


def make_snapshot(
    *,
    dept_id: UUID,
    cycle_days: int,
    project_type_id: UUID,
) -> BenchmarkProjectSnapshot:
    return BenchmarkProjectSnapshot(
        id=uuid4(),
        category_id=None,
        closed_at=NOW,
        created_at=NOW.replace(day=1) if cycle_days == 29 else NOW,
        creator_id=None,
        dept_id=dept_id,
        expected_finish_date=date(2026, 12, 31),
        participant_user_ids=frozenset(),
        phase_durations_days=(2,),
        project_no="Z-2026-0001",
        project_type_id=project_type_id,
        spent_amount=Decimal("100.00"),
        tag_ids=(),
        task_count=10,
        overdue_task_count=1,
        total_budget=Decimal("100.00"),
        updated_at=NOW,
    ).with_cycle_days(cycle_days)
