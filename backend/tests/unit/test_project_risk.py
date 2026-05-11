from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.users import User, UserRole
from app.services.ai_audit import AiAuditLogger, InMemoryAiAuditLogRepository
from app.services.ai_providers import AiProviderService, FakeAiProvider
from app.services.project_benchmarks import (
    BenchmarkProjectSnapshot,
    InMemoryProjectBenchmarkRepository,
)
from app.services.project_risk import ProjectRiskService
from tests.factories import UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_project_risk_scores_normal_project_below_30() -> None:
    dept_id = uuid4()
    actor = user(UserRole.admin, dept_id)
    target = snapshot(dept_id=dept_id, expected_finish_date=date(2026, 12, 31))
    service = ProjectRiskService(
        repository=InMemoryProjectBenchmarkRepository([target]),
        now_provider=lambda: NOW,
    )

    result = await service.analyze_project(actor=actor, project_id=target.id)

    assert result.score < 30
    assert result.level == "low"
    assert result.summary.source == "rules"


@pytest.mark.asyncio
async def test_project_risk_scores_over_budget_overdue_project_above_70() -> None:
    dept_id = uuid4()
    actor = user(UserRole.admin, dept_id)
    target = snapshot(
        budget_variance_percent=80,
        dept_id=dept_id,
        expected_finish_date=date(2026, 5, 1),
        overdue_task_count=8,
        task_count=10,
    )
    service = ProjectRiskService(
        repository=InMemoryProjectBenchmarkRepository([target]),
        now_provider=lambda: NOW,
    )

    result = await service.analyze_project(actor=actor, project_id=target.id)

    assert result.score > 70
    assert result.level in {"high", "critical"}
    assert {reason.code for reason in result.reasons} >= {
        "budget_variance",
        "schedule_delay",
        "task_overdue",
    }


@pytest.mark.asyncio
async def test_project_risk_returns_rule_summary_when_ai_is_disabled() -> None:
    dept_id = uuid4()
    actor = user(UserRole.admin, dept_id)
    target = snapshot(budget_variance_percent=30, dept_id=dept_id)
    service = ProjectRiskService(
        ai_service=AiProviderService(
            audit_logger=AiAuditLogger(InMemoryAiAuditLogRepository()),
            provider=FakeAiProvider({"risk_summary": {"summary": "AI", "recommendations": []}}),
            settings=Settings(),
        ),
        repository=InMemoryProjectBenchmarkRepository([target]),
        now_provider=lambda: NOW,
    )

    result = await service.analyze_project(actor=actor, project_id=target.id)

    assert result.summary.source == "rules"
    assert "预算" in result.summary.text


@pytest.mark.asyncio
async def test_project_risk_falls_back_when_ai_returns_invalid_schema() -> None:
    dept_id = uuid4()
    actor = user(UserRole.admin, dept_id)
    target = snapshot(budget_variance_percent=30, dept_id=dept_id)
    audit_repository = InMemoryAiAuditLogRepository()
    service = ProjectRiskService(
        ai_service=AiProviderService(
            audit_logger=AiAuditLogger(audit_repository),
            provider=FakeAiProvider({"risk_summary": {"recommendations": ["缺少摘要"]}}),
            settings=Settings(ai_enabled=True, ai_provider="fake", ai_model="fake-risk"),
        ),
        repository=InMemoryProjectBenchmarkRepository([target]),
        now_provider=lambda: NOW,
    )

    result = await service.analyze_project(actor=actor, project_id=target.id)

    assert result.summary.source == "rules"
    assert audit_repository.entries[-1].status == "failed"
    assert audit_repository.entries[-1].error_code == "schema_validation_failed"


def user(role: UserRole, dept_id: UUID) -> User:
    return cast(User, UserFactory(role=role, dept_id=dept_id))


def snapshot(
    *,
    dept_id: UUID,
    budget_variance_percent: float = 0,
    expected_finish_date: date = date(2026, 12, 31),
    overdue_task_count: int = 0,
    task_count: int = 10,
) -> BenchmarkProjectSnapshot:
    total_budget = Decimal("100.00")
    spent_amount = total_budget * (Decimal("1") + Decimal(str(budget_variance_percent)) / 100)
    return BenchmarkProjectSnapshot(
        id=uuid4(),
        category_id=None,
        closed_at=None,
        created_at=NOW - timedelta(days=30),
        creator_id=None,
        dept_id=dept_id,
        expected_finish_date=expected_finish_date,
        participant_user_ids=frozenset(),
        phase_durations_days=(3,),
        project_no="Z-2026-0001",
        project_type_id=None,
        spent_amount=spent_amount,
        tag_ids=(),
        task_count=task_count,
        overdue_task_count=overdue_task_count,
        total_budget=total_budget,
        updated_at=NOW,
    )
