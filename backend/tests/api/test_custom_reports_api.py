from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.custom_reports import get_custom_report_audit_writer, get_custom_report_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.custom_reports import CustomReportShareScope
from app.models.users import User, UserRole, UserStatus
from app.services.audit import InMemoryAuditLogWriter
from app.services.custom_reports import (
    CustomReportQueryExecutor,
    CustomReportService,
    InMemoryCustomReportRepository,
)
from app.services.report_query_compiler import CompiledReportQuery

NOW = datetime(2026, 5, 12, 9, 0, tzinfo=UTC)


def make_user(
    role: UserRole,
    *,
    username: str,
    dept_id: UUID | None = None,
) -> User:
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=dept_id,
        status=UserStatus.active,
        password_changed_at=NOW,
        last_login_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


class StaticQueryExecutor(CustomReportQueryExecutor):
    def __init__(self, rows: Sequence[Mapping[str, object]] | None = None) -> None:
        self.rows = list(rows or [{"project_no": "Z-2026-0001"}])
        self.calls = 0

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        self.calls += 1
        return [dict(row) for row in self.rows]


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
    app.dependency_overrides[get_custom_report_audit_writer] = InMemoryAuditLogWriter
    return TestClient(app)


def make_service(
    *,
    executor: StaticQueryExecutor | None = None,
) -> tuple[CustomReportService, InMemoryCustomReportRepository, StaticQueryExecutor]:
    repository = InMemoryCustomReportRepository(now_provider=lambda: NOW)
    query_executor = executor or StaticQueryExecutor()
    return (
        CustomReportService(
            repository=repository,
            query_executor=query_executor,
            now_provider=lambda: NOW,
        ),
        repository,
        query_executor,
    )


def test_custom_reports_api_lists_datasets_previews_and_creates_report() -> None:
    admin = make_user(UserRole.admin, username="admin")
    service, _repository, _executor = make_service()
    client = build_client(admin, service)

    datasets_response = client.get("/api/v1/custom-reports/datasets")
    preview_response = client.post(
        "/api/v1/custom-reports/preview",
        json={"dataset": "project_overview", "dimensions": ["project_no"], "limit": 10},
    )
    create_response = client.post(
        "/api/v1/custom-reports",
        json={
            "name": "项目概览",
            "query_config": {"dataset": "project_overview", "dimensions": ["project_no"]},
            "chart_type": "table",
            "share_scope": "global",
        },
    )

    assert datasets_response.status_code == 200
    assert datasets_response.json()["data"][0]["key"] == "document_upload"
    assert preview_response.status_code == 200
    assert preview_response.json()["data"]["rows"] == [{"project_no": "Z-2026-0001"}]
    assert preview_response.json()["data"]["columns"][0]["key"] == "project_no"
    assert create_response.status_code == 200
    assert create_response.json()["data"]["share_scope"] == "global"


def test_custom_reports_api_rejects_global_create_for_project_member() -> None:
    member = make_user(UserRole.proj_member, username="member")
    service, _repository, _executor = make_service()
    client = build_client(member, service)

    response = client.post(
        "/api/v1/custom-reports",
        json={
            "name": "成员报表",
            "query_config": {"dataset": "project_overview", "dimensions": ["project_no"]},
            "share_scope": "global",
        },
    )

    assert response.status_code == 403


def test_custom_reports_api_rejects_invalid_preview_before_execution() -> None:
    admin = make_user(UserRole.admin, username="admin")
    executor = StaticQueryExecutor()
    service, _repository, executor = make_service(executor=executor)
    client = build_client(admin, service)

    response = client.post(
        "/api/v1/custom-reports/preview",
        json={"dataset": "project_overview", "dimensions": ["not_registered"]},
    )

    assert response.status_code == 422
    assert executor.calls == 0


def test_custom_reports_api_filters_department_share_and_blocks_deleted_preview() -> None:
    dept_a = uuid4()
    dept_b = uuid4()
    owner = make_user(UserRole.dept_manager, username="owner", dept_id=dept_a)
    peer = make_user(UserRole.proj_member, username="peer", dept_id=dept_a)
    outsider = make_user(UserRole.proj_member, username="outsider", dept_id=dept_b)
    service, _repository, _executor = make_service()
    owner_client = build_client(owner, service)

    create_response = owner_client.post(
        "/api/v1/custom-reports",
        json={
            "name": "部门报表",
            "query_config": {"dataset": "project_overview", "dimensions": ["project_no"]},
            "share_scope": CustomReportShareScope.department.value,
        },
    )
    report_id = create_response.json()["data"]["id"]

    peer_list = build_client(peer, service).get("/api/v1/custom-reports")
    outsider_list = build_client(outsider, service).get("/api/v1/custom-reports")
    delete_response = owner_client.delete(f"/api/v1/custom-reports/{report_id}")
    deleted_preview = owner_client.post(f"/api/v1/custom-reports/{report_id}/preview")

    assert create_response.status_code == 200
    assert [item["id"] for item in peer_list.json()["data"]] == [report_id]
    assert outsider_list.json()["data"] == []
    assert delete_response.status_code == 200
    assert deleted_preview.status_code == 404
