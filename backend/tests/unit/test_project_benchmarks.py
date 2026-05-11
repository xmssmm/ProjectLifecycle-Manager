from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import PermissionDeniedError
from app.models.users import User, UserRole
from app.services.project_benchmarks import (
    BenchmarkProjectSnapshot,
    InMemoryProjectBenchmarkRepository,
    ProjectBenchmarkService,
)
from tests.factories import UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_project_benchmark_returns_insufficient_sample_when_peer_count_is_low() -> None:
    dept_id = uuid4()
    type_id = uuid4()
    admin = user(role=UserRole.admin, dept_id=dept_id)
    target = snapshot(dept_id=dept_id, project_type_id=type_id, cycle_days=15)
    samples = [
        snapshot(dept_id=dept_id, project_type_id=type_id, cycle_days=days)
        for days in [10, 20, 30, 40]
    ]
    service = ProjectBenchmarkService(
        repository=InMemoryProjectBenchmarkRepository([target, *samples]),
        min_sample_size=5,
        now_provider=lambda: NOW,
    )

    result = await service.analyze_project(actor=admin, project_id=target.id)

    assert result.status == "insufficient_sample"
    assert result.sample_count == 4
    assert result.metric("cycle_days").average is None


@pytest.mark.asyncio
async def test_project_benchmark_calculates_peer_percentiles() -> None:
    dept_id = uuid4()
    type_id = uuid4()
    admin = user(role=UserRole.admin, dept_id=dept_id)
    target = snapshot(
        dept_id=dept_id,
        project_type_id=type_id,
        budget_variance_percent=20,
        cycle_days=15,
        phase_stay_days=6,
        task_overdue_rate=50,
    )
    samples = [
        snapshot(
            dept_id=dept_id,
            project_type_id=type_id,
            budget_variance_percent=value - 10,
            cycle_days=value,
            phase_stay_days=value / 10,
            task_overdue_rate=value - 10,
        )
        for value in [10, 20, 30, 40, 50]
    ]
    service = ProjectBenchmarkService(
        repository=InMemoryProjectBenchmarkRepository([target, *samples]),
        min_sample_size=5,
        now_provider=lambda: NOW,
    )

    result = await service.analyze_project(actor=admin, project_id=target.id)
    cycle = result.metric("cycle_days")
    budget = result.metric("budget_variance_percent")
    overdue = result.metric("task_overdue_rate")
    phase = result.metric("phase_stay_days")

    assert result.status == "ready"
    assert cycle.sample_count == 5
    assert cycle.current_value == pytest.approx(15)
    assert cycle.average == pytest.approx(30)
    assert cycle.p50 == pytest.approx(30)
    assert cycle.p90 == pytest.approx(46)
    assert budget.p90 == pytest.approx(36)
    assert overdue.current_value == pytest.approx(50)
    assert phase.average == pytest.approx(3)


@pytest.mark.asyncio
async def test_project_benchmark_filters_samples_by_actor_visibility() -> None:
    dept_id = uuid4()
    type_id = uuid4()
    member = user(role=UserRole.proj_member, dept_id=dept_id)
    admin = user(role=UserRole.admin, dept_id=dept_id)
    target = snapshot(
        dept_id=dept_id,
        participant_user_ids=[member.id],
        project_type_id=type_id,
    )
    visible_to_member = snapshot(
        dept_id=dept_id,
        participant_user_ids=[member.id],
        project_type_id=type_id,
    )
    admin_only_samples = [
        snapshot(dept_id=dept_id, project_type_id=type_id, cycle_days=days)
        for days in [20, 30, 40, 50]
    ]
    service = ProjectBenchmarkService(
        repository=InMemoryProjectBenchmarkRepository(
            [target, visible_to_member, *admin_only_samples],
        ),
        min_sample_size=5,
        now_provider=lambda: NOW,
    )

    admin_result = await service.analyze_project(actor=admin, project_id=target.id)
    member_result = await service.analyze_project(actor=member, project_id=target.id)

    assert admin_result.sample_count == 5
    assert admin_result.status == "ready"
    assert member_result.sample_count == 1
    assert member_result.status == "insufficient_sample"


@pytest.mark.asyncio
async def test_project_benchmark_rejects_invisible_target_project() -> None:
    target = snapshot(dept_id=uuid4())
    outsider = user(role=UserRole.proj_member, dept_id=uuid4())
    service = ProjectBenchmarkService(
        repository=InMemoryProjectBenchmarkRepository([target]),
        min_sample_size=1,
        now_provider=lambda: NOW,
    )

    with pytest.raises(PermissionDeniedError):
        await service.analyze_project(actor=outsider, project_id=target.id)


def user(*, role: UserRole, dept_id: UUID | None = None) -> User:
    return cast(User, UserFactory(role=role, dept_id=dept_id))


def snapshot(
    *,
    dept_id: UUID,
    budget_variance_percent: float = 0,
    category_id: UUID | None = None,
    cycle_days: float = 10,
    participant_user_ids: list[UUID] | None = None,
    phase_stay_days: float = 2,
    project_type_id: UUID | None = None,
    tag_ids: list[UUID] | None = None,
    task_overdue_rate: float = 0,
) -> BenchmarkProjectSnapshot:
    created_at = NOW - timedelta(days=int(cycle_days))
    total_budget = Decimal("100.00")
    spent_amount = total_budget * (Decimal("1") + Decimal(str(budget_variance_percent)) / 100)
    return BenchmarkProjectSnapshot(
        id=uuid4(),
        category_id=category_id,
        closed_at=NOW,
        created_at=created_at,
        creator_id=None,
        dept_id=dept_id,
        expected_finish_date=date(2026, 12, 31),
        participant_user_ids=frozenset(participant_user_ids or []),
        phase_durations_days=(phase_stay_days,),
        project_no="Z-2026-0001",
        project_type_id=project_type_id,
        spent_amount=spent_amount,
        tag_ids=tuple(tag_ids or []),
        task_count=10,
        overdue_task_count=int(task_overdue_rate / 10),
        total_budget=total_budget,
        updated_at=NOW,
    )
