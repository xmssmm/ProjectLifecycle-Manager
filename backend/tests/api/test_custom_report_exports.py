from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.custom_reports import get_custom_report_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.custom_reports import (
    CustomReportDefinition,
    CustomReportRun,
    CustomReportRunStatus,
    CustomReportShareScope,
)
from app.models.users import User, UserRole
from app.services.custom_reports import (
    CustomReportQueryExecutor,
    CustomReportService,
    InMemoryCustomReportRepository,
)
from app.services.report_query_compiler import CompiledReportQuery
from app.storage.base import StorageBackend
from tests.factories import UserFactory


class StaticStorage(StorageBackend):
    def __init__(self, content: bytes) -> None:
        self.content = content

    def save(self, *, sub_id: str, phase_id: str, filename: str, content: bytes) -> str:
        _ = (sub_id, phase_id, filename, content)
        return "custom-reports/report/custom_report.zip"

    def read(self, storage_key: str) -> bytes:
        assert storage_key == "custom-reports/report/custom_report.zip"
        return self.content

    def delete(self, storage_key: str) -> None:
        _ = storage_key

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


class NoopQueryExecutor(CustomReportQueryExecutor):
    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        _ = compiled
        return []


def test_custom_report_run_download_allows_shared_users_and_blocks_private_outsider() -> None:
    dept_id = uuid4()
    owner = cast(User, UserFactory(role=UserRole.dept_manager, dept_id=dept_id))
    peer = cast(User, UserFactory(role=UserRole.proj_member, dept_id=dept_id))
    outsider = cast(User, UserFactory(role=UserRole.proj_member, dept_id=uuid4()))
    private_report = make_report(owner, share_scope=CustomReportShareScope.private)
    department_report = make_report(
        owner,
        share_scope=CustomReportShareScope.department,
        owner_dept_id=peer.dept_id,
    )
    private_run = make_run(private_report)
    department_run = make_run(department_report)
    service = CustomReportService(
        repository=InMemoryCustomReportRepository(
            reports=[private_report, department_report],
            runs=[private_run, department_run],
            users=[owner, peer, outsider],
        ),
        query_executor=NoopQueryExecutor(),
        storage=StaticStorage(b"zip-bytes"),
    )

    owner_response = build_client(owner, service).get(
        f"/api/v1/custom-reports/runs/{private_run.id}/download",
    )
    peer_response = build_client(peer, service).get(
        f"/api/v1/custom-reports/runs/{department_run.id}/download",
    )
    outsider_response = build_client(outsider, service).get(
        f"/api/v1/custom-reports/runs/{private_run.id}/download",
    )

    assert owner_response.status_code == 200
    assert owner_response.content == b"zip-bytes"
    assert owner_response.headers["content-type"].startswith("application/zip")
    assert "custom_report.zip" in owner_response.headers["content-disposition"]
    assert peer_response.status_code == 200
    assert outsider_response.status_code == 403


def build_client(user: User, service: CustomReportService) -> TestClient:
    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> CustomReportService:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_custom_report_service] = fake_service
    return TestClient(app)


def make_report(
    owner: User,
    *,
    share_scope: CustomReportShareScope,
    owner_dept_id: UUID | None = None,
) -> CustomReportDefinition:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    return CustomReportDefinition(
        id=uuid4(),
        name="项目概览",
        description=None,
        owner_id=owner.id,
        owner_dept_id=owner_dept_id or owner.dept_id,
        dataset="project_overview",
        query_config={"dataset": "project_overview", "dimensions": ["project_no"]},
        chart_type="table",
        share_scope=share_scope,
        schedule_frequency=None,
        schedule_time=None,
        schedule_day_of_week=None,
        schedule_day_of_month=None,
        schedule_timezone=None,
        last_run_at=None,
        next_run_at=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_run(report: CustomReportDefinition) -> CustomReportRun:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    return CustomReportRun(
        id=uuid4(),
        report_id=report.id,
        triggered_by_id=report.owner_id,
        status=CustomReportRunStatus.completed,
        row_count=1,
        storage_key="custom-reports/report/custom_report.zip",
        file_format="zip",
        error_message=None,
        started_at=now,
        finished_at=now,
        created_at=now,
        updated_at=now,
    )
