from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.workflows import get_workflow_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.project_types import ProjectType
from app.models.users import User, UserRole, UserStatus
from app.models.workflows import WorkflowTemplateStatus, WorkflowTemplateVersion
from app.schemas.workflows import ProjectTypeCreate

NOW = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def make_user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        username=f"{role.value}-{uuid4().hex[:6]}",
        email=None,
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=NOW,
        last_login_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_project_type() -> ProjectType:
    return ProjectType(
        id=uuid4(),
        code="research",
        name="科研项目",
        description="科研项目流程",
        is_builtin=False,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


def make_template_version() -> WorkflowTemplateVersion:
    return WorkflowTemplateVersion(
        id=uuid4(),
        template_id=uuid4(),
        version_no=2,
        status=WorkflowTemplateStatus.published,
        phase_definitions=[
            {
                "key": "proposal",
                "name": "课题申报",
                "order": 1,
                "required_documents": [],
                "allow_parallel": False,
                "entry_rules": {},
            },
        ],
        published_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


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
    app.dependency_overrides[get_workflow_service] = fake_service
    return TestClient(app)


def test_workflow_api_lists_and_creates_project_types_for_admin() -> None:
    admin = make_user(UserRole.admin)
    project_type = make_project_type()

    class FakeWorkflowService:
        async def list_project_types(self) -> list[ProjectType]:
            return [project_type]

        async def create_project_type(
            self,
            *,
            actor: User,
            payload: object,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> ProjectType:
            assert actor.id == admin.id
            assert cast(ProjectTypeCreate, payload).code == "research"
            assert audit_writer is not None
            assert audit_context is not None
            return project_type

    client = build_client(admin, FakeWorkflowService())

    list_response = client.get("/api/v1/workflows/project-types")
    create_response = client.post(
        "/api/v1/workflows/project-types",
        json={"code": "research", "name": "科研项目", "description": "科研项目流程"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["code"] == "research"
    assert create_response.status_code == 200
    assert create_response.json()["data"]["name"] == "科研项目"


def test_workflow_api_publishes_template_version_for_admin() -> None:
    admin = make_user(UserRole.admin)
    version = make_template_version()

    class FakeWorkflowService:
        async def publish_template_version(
            self,
            *,
            actor: User,
            version_id: object,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> WorkflowTemplateVersion:
            assert actor.id == admin.id
            assert str(version_id) == str(version.id)
            assert audit_writer is not None
            assert audit_context is not None
            return version

    client = build_client(admin, FakeWorkflowService())

    response = client.post(f"/api/v1/workflows/template-versions/{version.id}/publish")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "published"
    assert response.json()["data"]["phase_definitions"][0]["key"] == "proposal"


def test_workflow_api_rejects_non_admin_users() -> None:
    client = build_client(make_user(UserRole.dept_manager), object())

    list_response = client.get("/api/v1/workflows/project-types")
    create_response = client.post(
        "/api/v1/workflows/project-types",
        json={"code": "research", "name": "科研项目"},
    )
    publish_response = client.post(f"/api/v1/workflows/template-versions/{uuid4()}/publish")

    assert list_response.status_code == 403
    assert create_response.status_code == 403
    assert publish_response.status_code == 403
