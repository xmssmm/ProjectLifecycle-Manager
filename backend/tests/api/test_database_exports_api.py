from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.exports import get_database_export_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.exports import DatabaseExportJob, DatabaseExportJobStatus
from app.models.users import User, UserRole, UserStatus
from app.services.database_exports import DatabaseExportDownload

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


def make_job(admin: User) -> DatabaseExportJob:
    return DatabaseExportJob(
        id=uuid4(),
        requested_by_id=admin.id,
        status=DatabaseExportJobStatus.completed,
        progress=100,
        table_count=2,
        row_count=2,
        storage_key="exports/job/database_export.zip",
        manifest={"total_rows": 2},
        error_message=None,
        started_at=NOW,
        finished_at=NOW,
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
    app.dependency_overrides[get_database_export_service] = fake_service
    return TestClient(app)


def test_database_export_api_creates_reads_and_downloads_for_admin() -> None:
    admin = make_user(UserRole.admin)
    job = make_job(admin)

    class FakeDatabaseExportService:
        async def create_export(
            self,
            *,
            actor: User,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> DatabaseExportJob:
            assert actor.id == admin.id
            assert audit_writer is not None
            assert audit_context is not None
            return job

        async def get_export_job(self, *, actor: User, job_id: UUID) -> DatabaseExportJob:
            assert actor.id == admin.id
            assert job_id == job.id
            return job

        async def download_export(
            self,
            *,
            actor: User,
            job_id: UUID,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> DatabaseExportDownload:
            assert actor.id == admin.id
            assert job_id == job.id
            assert audit_writer is not None
            assert audit_context is not None
            return DatabaseExportDownload(
                file_name="database_export.zip",
                content_type="application/zip",
                content=b"PK-export",
            )

    client = build_client(admin, FakeDatabaseExportService())

    create_response = client.post("/api/v1/exports/database")
    detail_response = client.get(f"/api/v1/exports/database/{job.id}")
    download_response = client.get(f"/api/v1/exports/database/{job.id}/download")

    assert create_response.status_code == 200
    assert create_response.json()["data"]["download_url"].endswith(f"/{job.id}/download")
    assert detail_response.json()["data"]["status"] == "completed"
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"
    assert download_response.content == b"PK-export"


def test_database_export_api_rejects_non_admin() -> None:
    client = build_client(make_user(UserRole.dept_manager), object())

    create_response = client.post("/api/v1/exports/database")
    detail_response = client.get(f"/api/v1/exports/database/{uuid4()}")
    download_response = client.get(f"/api/v1/exports/database/{uuid4()}/download")

    assert create_response.status_code == 403
    assert detail_response.status_code == 403
    assert download_response.status_code == 403
