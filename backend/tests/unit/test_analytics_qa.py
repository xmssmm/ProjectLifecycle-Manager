from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import ValidationFailedError
from app.models.users import User, UserRole
from app.services.ai_audit import AiAuditLogger, InMemoryAiAuditLogRepository
from app.services.ai_providers import AiProviderService, FakeAiProvider
from app.services.analytics_qa import AnalyticsQaService
from app.services.report_query_compiler import CompiledReportQuery
from tests.factories import UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


class RecordingAnalyticsExecutor:
    def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
        self.compiled: CompiledReportQuery | None = None
        self.rows = [dict(row) for row in rows]

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        self.compiled = compiled
        return self.rows


@pytest.mark.asyncio
async def test_builtin_department_project_count_question_works_when_ai_is_disabled() -> None:
    dept_id = uuid4()
    actor = cast(User, UserFactory(role=UserRole.dept_manager, dept_id=dept_id))
    executor = RecordingAnalyticsExecutor([{"project_count": 3}])
    service = AnalyticsQaService(
        query_executor=executor,
        now_provider=lambda: NOW,
    )

    result = await service.answer_question(actor=actor, question="本部门今年项目数")

    assert result.source == "rules"
    assert result.answer == "本部门今年项目数为 3 个。"
    assert result.query_config.dataset == "project_overview"
    assert result.rows == [{"project_count": 3}]
    assert executor.compiled is not None


@pytest.mark.asyncio
async def test_ai_unknown_dataset_is_rejected_before_execution() -> None:
    actor = cast(User, UserFactory(role=UserRole.admin))
    executor = RecordingAnalyticsExecutor([])
    ai_service = AiProviderService(
        audit_logger=AiAuditLogger(InMemoryAiAuditLogRepository()),
        provider=FakeAiProvider(
            {
                "analytics_query_config": {
                    "answer_template": "bad",
                    "chart_type": "table",
                    "query_config": {
                        "dataset": "raw_sql",
                        "dimensions": ["id"],
                        "filters": [],
                        "limit": 10,
                        "metrics": [],
                        "sort": [],
                    },
                },
            },
        ),
        settings=Settings(ai_enabled=True, ai_provider="fake"),
    )
    service = AnalyticsQaService(ai_service=ai_service, query_executor=executor)

    with pytest.raises(ValidationFailedError):
        await service.answer_question(actor=actor, question="直接查数据库")

    assert executor.compiled is None


@pytest.mark.asyncio
async def test_answer_query_is_limited_by_current_user_scope() -> None:
    actor_id = uuid4()
    actor = cast(User, UserFactory(id=actor_id, role=UserRole.proj_member))
    executor = RecordingAnalyticsExecutor(
        [{"overdue_task_count": 4, "sub_project_id": str(uuid4())}],
    )
    service = AnalyticsQaService(query_executor=executor)

    result = await service.answer_question(actor=actor, question="逾期任务最多的项目")

    assert result.query_config.dataset == "task_overdue"
    assert executor.compiled is not None
    assert executor.compiled.scope.mode == "owned_sub_projects"
    assert executor.compiled.bound_parameters["actor_id"] == actor.id
    assert "4" in result.answer
