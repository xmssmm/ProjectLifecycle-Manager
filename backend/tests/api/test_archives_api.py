from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.archives import get_archive_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import ResourceConflictError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.archives import ArchiveBatch, ArchiveMainProject, ArchiveSubProject
from app.models.users import User, UserRole, UserStatus
from app.services.archives import ArchiveBatchDetail, ArchiveCandidate, ArchiveRunResult

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
    app.dependency_overrides[get_archive_service] = fake_service
    return TestClient(app)


def test_archive_api_lists_candidates_and_creates_batch_for_admin() -> None:
    admin = make_user(UserRole.admin)
    batch_id = uuid4()

    class FakeArchiveService:
        async def list_candidates(self) -> list[ArchiveCandidate]:
            return [
                ArchiveCandidate(
                    main_project_id=uuid4(),
                    project_no="Z-2022-0001",
                    name="Main Z-2022-0001",
                    closed_at=NOW,
                    sub_project_count=2,
                ),
            ]

        async def archive_eligible_projects(
            self,
            *,
            actor_id: UUID | None = None,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> ArchiveRunResult:
            assert actor_id == admin.id
            assert audit_writer is not None
            assert audit_context is not None
            return ArchiveRunResult(
                batch_id=batch_id,
                batch_no="ARCH-20260511-ABCDEF12",
                archived_main_project_count=1,
                archived_sub_project_count=2,
                main_projects_before=5,
                main_projects_after=4,
                duration_ms=13,
            )

    client = build_client(admin, FakeArchiveService())

    candidates_response = client.get("/api/v1/archives/candidates")
    create_response = client.post("/api/v1/archives/batches")

    assert candidates_response.status_code == 200
    assert candidates_response.json()["data"][0]["project_no"] == "Z-2022-0001"
    assert create_response.status_code == 200
    assert create_response.json()["data"]["batch_no"] == "ARCH-20260511-ABCDEF12"
    assert create_response.json()["data"]["archived_sub_project_count"] == 2


def test_archive_api_rejects_non_admin_archive_and_restore() -> None:
    client = build_client(make_user(UserRole.dept_manager), object())

    archive_response = client.post("/api/v1/archives/batches")
    restore_response = client.post(f"/api/v1/archives/main-projects/{uuid4()}/restore")

    assert archive_response.status_code == 403
    assert restore_response.status_code == 403


def test_archive_api_returns_restore_conflict_fields() -> None:
    admin = make_user(UserRole.admin)

    class FakeArchiveService:
        async def restore_main_project(
            self,
            *,
            actor: User,
            archive_main_project_id: UUID,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> object:
            assert actor.id == admin.id
            assert audit_writer is not None
            assert audit_context is not None
            raise ResourceConflictError(
                "恢复主项目存在唯一键冲突",
                data={"fields": ["project_no"], "project_no": "Z-2022-0001"},
            )

    client = build_client(admin, FakeArchiveService())

    response = client.post(f"/api/v1/archives/main-projects/{uuid4()}/restore")

    assert response.status_code == 409
    assert response.json()["data"] == {
        "fields": ["project_no"],
        "project_no": "Z-2022-0001",
    }


def test_archive_api_reads_batch_detail() -> None:
    admin = make_user(UserRole.admin)
    batch = ArchiveBatch(
        id=uuid4(),
        batch_no="ARCH-20260511-ABCDEF12",
        created_by_id=admin.id,
        status="completed",
        archived_main_project_count=1,
        archived_sub_project_count=1,
        duration_ms=12,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    archive_main = ArchiveMainProject(
        id=uuid4(),
        batch_id=batch.id,
        original_id=uuid4(),
        project_no="Z-2022-0001",
        name="Main Z-2022-0001",
        status="closed",
        closed_at=NOW,
        snapshot={"project_no": "Z-2022-0001"},
        archived_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    archive_sub = ArchiveSubProject(
        id=uuid4(),
        batch_id=batch.id,
        original_id=uuid4(),
        original_main_project_id=archive_main.original_id,
        project_no="Z-2022-0001-ZX-001",
        name="Sub Z-2022-0001-ZX-001",
        status="closed",
        closed_at=NOW,
        snapshot={"project_no": "Z-2022-0001-ZX-001"},
        archived_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    class FakeArchiveService:
        async def get_batch_detail(self, batch_id: UUID) -> ArchiveBatchDetail:
            assert batch_id == batch.id
            return ArchiveBatchDetail(
                batch=batch,
                main_projects=[archive_main],
                sub_projects=[archive_sub],
            )

    client = build_client(admin, FakeArchiveService())

    response = client.get(f"/api/v1/archives/batches/{batch.id}")

    assert response.status_code == 200
    assert response.json()["data"]["batch"]["batch_no"] == "ARCH-20260511-ABCDEF12"
    assert response.json()["data"]["main_projects"][0]["project_no"] == "Z-2022-0001"
    assert response.json()["data"]["sub_projects"][0]["project_no"] == "Z-2022-0001-ZX-001"
