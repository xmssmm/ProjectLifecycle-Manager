from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.departments import Department
from app.models.users import User, UserRole, UserStatus
from app.seeds.phase_doc_templates import seed_phase_doc_templates
from app.services.acceptance_steps import AcceptanceStepService, SqlAlchemyAcceptanceStepRepository
from app.services.audit import InMemoryAuditLogWriter
from app.services.documents import DocumentService, SqlAlchemyDocumentRepository
from app.services.main_projects import MainProjectService, SqlAlchemyMainProjectRepository
from app.services.notifications import NotificationService, SqlAlchemyNotificationRepository
from app.services.payments import PaymentService, SqlAlchemyPaymentRepository
from app.services.phases import PhaseService, SqlAlchemyPhaseRepository
from app.services.revoke_requests import RevokeRequestService, SqlAlchemyRevokeRequestRepository
from app.services.sub_projects import SqlAlchemySubProjectRepository, SubProjectService
from app.storage.base import StorageBackend

BUSINESS_DATE = date(2026, 5, 10)


class RecordingStorage(StorageBackend):
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def save(self, *, sub_id: str, phase_id: str, filename: str, content: bytes) -> str:
        key = f"{sub_id}/{phase_id}/{len(self.saved) + 1}-{filename}"
        self.saved[key] = content
        return key

    def read(self, storage_key: str) -> bytes:
        return self.saved[storage_key]

    def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)
        self.saved.pop(storage_key, None)

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


@dataclass
class E2EContext:
    session: AsyncSession
    department: Department
    admin: User
    dept_manager: User
    finance: User
    leader: User
    new_leader: User
    member: User
    storage: RecordingStorage = field(default_factory=RecordingStorage)
    audit_writer: InMemoryAuditLogWriter = field(default_factory=InMemoryAuditLogWriter)

    def notification_service(self) -> NotificationService:
        return NotificationService(
            repository=SqlAlchemyNotificationRepository(self.session),
            business_date_provider=lambda: BUSINESS_DATE,
        )

    def main_projects(self) -> MainProjectService:
        return MainProjectService(
            repository=SqlAlchemyMainProjectRepository(self.session),
            notification_service=self.notification_service(),
            today_provider=lambda: BUSINESS_DATE,
        )

    def sub_projects(self) -> SubProjectService:
        return SubProjectService(
            repository=SqlAlchemySubProjectRepository(self.session),
            notification_service=self.notification_service(),
            today_provider=lambda: BUSINESS_DATE,
        )

    def phases(self) -> PhaseService:
        return PhaseService(
            repository=SqlAlchemyPhaseRepository(self.session),
            notification_service=self.notification_service(),
            today_provider=lambda: BUSINESS_DATE,
        )

    def documents(self) -> DocumentService:
        return DocumentService(
            repository=SqlAlchemyDocumentRepository(self.session),
            storage=self.storage,
            max_file_size_bytes=1024 * 1024,
        )

    def payments(self) -> PaymentService:
        return PaymentService(
            repository=SqlAlchemyPaymentRepository(self.session),
            storage=self.storage,
            notification_service=self.notification_service(),
            max_file_size_bytes=1024 * 1024,
            today_provider=lambda: BUSINESS_DATE,
        )

    def revoke_requests(self) -> RevokeRequestService:
        return RevokeRequestService(
            repository=SqlAlchemyRevokeRequestRepository(self.session),
            notification_service=self.notification_service(),
        )

    def acceptance_steps(self) -> AcceptanceStepService:
        return AcceptanceStepService(
            repository=SqlAlchemyAcceptanceStepRepository(self.session),
        )


@pytest.fixture()
async def e2e_session(postgres_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(postgres_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP SEQUENCE IF EXISTS main_project_no_seq"))
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                text("CREATE SEQUENCE main_project_no_seq START WITH 1 INCREMENT BY 1"),
            )

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await seed_phase_doc_templates(session)
            await session.commit()
            yield session
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP SEQUENCE IF EXISTS main_project_no_seq"))
        await engine.dispose()


@pytest.fixture()
async def e2e_context(e2e_session: AsyncSession) -> E2EContext:
    now = datetime.now(UTC)
    department = Department(
        id=uuid4(),
        code="OPS",
        name="Operations",
        created_at=now,
        updated_at=now,
    )
    users = [
        _make_user("admin", UserRole.admin, None, now),
        _make_user("manager", UserRole.dept_manager, department.id, now),
        _make_user("finance", UserRole.finance_manager, department.id, now),
        _make_user("leader", UserRole.proj_leader, department.id, now),
        _make_user("new-leader", UserRole.proj_leader, department.id, now),
        _make_user("member", UserRole.proj_member, department.id, now),
    ]
    e2e_session.add(department)
    e2e_session.add_all(users)
    await e2e_session.commit()
    return E2EContext(
        session=e2e_session,
        department=department,
        admin=users[0],
        dept_manager=users[1],
        finance=users[2],
        leader=users[3],
        new_leader=users[4],
        member=users[5],
    )


def _make_user(
    username: str,
    role: UserRole,
    dept_id: UUID | None,
    now: datetime,
) -> User:
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=dept_id,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )
