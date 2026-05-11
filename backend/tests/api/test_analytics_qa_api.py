from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

from app.api.v1.analytics_qa import get_analytics_qa_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole
from app.schemas.custom_reports import ReportMetricConfig, ReportQueryConfig
from app.services.analytics_qa import AnalyticsQaAnswer, AnalyticsQaChartSuggestion
from app.services.report_datasets import DatasetAggregate
from tests.factories import UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


def test_analytics_qa_api_returns_answer_table_and_chart() -> None:
    actor = cast(User, UserFactory(role=UserRole.admin))

    class FakeAnalyticsQaService:
        async def answer_question(self, *, actor: User, question: str) -> AnalyticsQaAnswer:
            assert actor.id == actor_id
            assert question == "本部门今年项目数"
            return AnalyticsQaAnswer(
                answer="本部门今年项目数为 3 个。",
                chart=AnalyticsQaChartSuggestion(
                    type="stat",
                    x_field=None,
                    y_field="project_count",
                ),
                columns=[],
                query_config=ReportQueryConfig(
                    dataset="project_overview",
                    metrics=[
                        ReportMetricConfig(
                            aggregate=DatasetAggregate.count,
                            alias="project_count",
                            field="id",
                        ),
                    ],
                ),
                question=question,
                row_count=1,
                rows=[{"project_count": 3}],
                source="rules",
            )

    actor_id = actor.id
    response = build_client(actor, FakeAnalyticsQaService()).post(
        "/api/v1/analytics-qa/ask",
        json={"question": "本部门今年项目数"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["answer"] == "本部门今年项目数为 3 个。"
    assert payload["chart"]["type"] == "stat"
    assert payload["rows"] == [{"project_count": 3}]


def build_client(user: User, service: object) -> TestClient:
    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> object:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_analytics_qa_service] = fake_service
    return TestClient(app)
