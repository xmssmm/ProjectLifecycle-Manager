from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.project_templates import (
    get_project_template_audit_writer,
    get_project_template_service,
)
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.users import User, UserRole
from app.services.audit import InMemoryAuditLogWriter
from app.services.project_templates import (
    InMemoryProjectTemplateRepository,
    ProjectTemplateService,
)
from tests.factories import MainProjectFactory, UserFactory


def test_project_template_api_creates_uses_and_filters_templates() -> None:
    dept_id = uuid4()
    admin = cast(User, UserFactory(role=UserRole.admin, dept_id=dept_id))
    manager = cast(User, UserFactory(role=UserRole.dept_manager, dept_id=dept_id))
    member = cast(User, UserFactory(role=UserRole.proj_member, dept_id=dept_id))
    source_project = cast(
        MainProject,
        MainProjectFactory(
            dept_id=dept_id,
            project_no="Z-2026-0007",
            name="历史档案平台",
            status=MainProjectStatus.completed,
            total_budget=Decimal("800000.00"),
            expected_finish_date=date(2026, 12, 31),
            creator_id=manager.id,
        ),
    )
    service = ProjectTemplateService(
        repository=InMemoryProjectTemplateRepository(
            projects=[source_project],
            users=[admin, manager, member],
            next_project_sequence=12,
        ),
        now_provider=lambda: datetime(2026, 6, 1, tzinfo=UTC),
        today_provider=lambda: date(2026, 6, 1),
    )
    audit_writer = InMemoryAuditLogWriter()
    admin_client = build_client(admin, service, audit_writer=audit_writer)

    category_response = admin_client.post(
        "/api/v1/project-templates/categories",
        json={"code": "software", "name": "软件项目"},
    )
    tag_response = admin_client.post(
        "/api/v1/project-templates/tags",
        json={"code": "archive", "name": "档案", "color": "#2f6fed"},
    )
    template_response = admin_client.post(
        "/api/v1/project-templates/templates/from-project",
        json={
            "category_id": category_response.json()["data"]["id"],
            "copy_document_requirements": True,
            "copy_phase_plan": True,
            "copy_task_checklist": True,
            "description": "来自已完成项目",
            "name": "档案平台模板",
            "scope": "department",
            "source_project_id": str(source_project.id),
            "tag_ids": [tag_response.json()["data"]["id"]],
        },
    )
    template_id = template_response.json()["data"]["id"]
    instantiate_response = admin_client.post(
        f"/api/v1/project-templates/templates/{template_id}/instantiate",
        json={"dept_id": str(dept_id), "name": "新档案平台"},
    )
    filtered_response = admin_client.get(
        f"/api/v1/project-templates/templates?tag_id={tag_response.json()['data']['id']}",
    )
    member_response = build_client(member, service, audit_writer=audit_writer).post(
        "/api/v1/project-templates/templates/from-project",
        json={
            "name": "成员全局模板",
            "scope": "global",
            "source_project_id": str(source_project.id),
        },
    )

    assert category_response.status_code == 200
    assert tag_response.status_code == 200
    assert template_response.status_code == 200
    template_payload = template_response.json()["data"]
    assert template_payload["source_project_no"] == "Z-2026-0007"
    assert template_payload["field_defaults"]["total_budget"] == "800000.00"
    assert "attachments" not in template_payload["field_defaults"]
    assert instantiate_response.status_code == 200
    created_project = instantiate_response.json()["data"]
    assert created_project["project_no"] == "Z-2026-0012"
    assert created_project["name"] == "新档案平台"
    assert created_project["total_budget"] == "800000.00"
    assert filtered_response.status_code == 200
    assert [item["id"] for item in filtered_response.json()["data"]] == [template_id]
    assert member_response.status_code == 403
    assert [entry.action for entry in audit_writer.entries] == [
        "project_template.create",
        "project_template.instantiate",
    ]


def build_client(
    user: User,
    service: ProjectTemplateService,
    *,
    audit_writer: InMemoryAuditLogWriter,
) -> TestClient:
    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> ProjectTemplateService:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_project_template_service] = fake_service
    app.dependency_overrides[get_project_template_audit_writer] = lambda: audit_writer
    return TestClient(app)
