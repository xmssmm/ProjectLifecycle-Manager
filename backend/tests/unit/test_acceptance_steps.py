from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table, UniqueConstraint

from app.api.v1.acceptance_steps import get_acceptance_step_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.acceptance_steps import AcceptanceStep, AcceptanceStepStatus
from app.models.base import Base
from app.models.documents import Document
from app.models.phases import Phase, PhaseDocRequirement, PhaseDocTemplate, PhaseStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.schemas.acceptance_steps import (
    AcceptanceStepCreate,
    AcceptanceStepRead,
    AcceptanceStepUpdate,
)
from app.services.acceptance_steps import (
    AcceptanceStepService,
    InMemoryAcceptanceStepRepository,
)
from app.services.phases import InMemoryPhaseRepository, PhaseService


def make_user(role: UserRole, *, username: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_sub_project(manager: User) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no="Z-2026-0001-ZX-001",
        name="采购实施",
        main_project_id=uuid4(),
        dept_id=uuid4(),
        budget=Decimal("100000.00"),
        manager_id=manager.id,
        creator_id=manager.id,
        status=SubProjectStatus.in_progress,
        plan_end_date=date(2026, 10, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark=None,
        created_at=now,
        updated_at=now,
    )


def make_phase(
    sub_project: SubProject,
    *,
    phase_no: int = 4,
    status: PhaseStatus = PhaseStatus.in_progress,
) -> Phase:
    now = datetime.now(UTC)
    codes = {
        1: ("initiation", "立项"),
        2: ("procurement", "采购"),
        3: ("contract", "合同"),
        4: ("acceptance", "验收"),
    }
    code, name = codes[phase_no]
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=phase_no,
        code=code,
        name=name,
        status=status,
        enter_at=now if status == PhaseStatus.in_progress else None,
        finish_at=None,
        procurement_type=None,
        created_at=now,
        updated_at=now,
    )


def make_member(sub_project: SubProject, user: User) -> SubProjectMember:
    return SubProjectMember(
        id=uuid4(),
        sub_project_id=sub_project.id,
        user_id=user.id,
        role_in_project=SubProjectMemberRole.proj_member,
        joined_at=datetime.now(UTC),
    )


def make_document(
    sub_project: SubProject,
    phase: Phase,
    step: AcceptanceStep,
    user: User,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        acceptance_step_id=step.id,
        doc_type="acceptance_report",
        file_name="acceptance.pdf",
        file_path=f"{sub_project.id}/{phase.id}/acceptance.pdf",
        file_size=256,
        version=1,
        is_latest=False,
        is_deleted=False,
        uploader_id=user.id,
        created_at=now,
        updated_at=now,
    )


def make_service() -> tuple[
    AcceptanceStepService,
    InMemoryAcceptanceStepRepository,
    User,
    User,
    SubProject,
    Phase,
]:
    leader = make_user(UserRole.proj_leader, username="leader")
    member = make_user(UserRole.proj_member, username="member")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    repository = InMemoryAcceptanceStepRepository(
        phases=[phase],
        sub_projects=[sub_project],
        members=[make_member(sub_project, leader), make_member(sub_project, member)],
    )
    service = AcceptanceStepService(repository=repository)
    return service, repository, leader, member, sub_project, phase


def test_acceptance_step_model_and_schema_match_requirements() -> None:
    assert [status.value for status in AcceptanceStepStatus] == [
        "not_started",
        "in_progress",
        "completed",
    ]
    assert "acceptance_steps" in Base.metadata.tables
    columns = set(AcceptanceStep.__table__.c.keys())
    assert {
        "id",
        "phase_id",
        "step_no",
        "step_name",
        "responsible_id",
        "plan_date",
        "description",
        "status",
        "completed_at",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert isinstance(AcceptanceStep.__table__, Table)
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("phase_id", "step_no")
        for constraint in AcceptanceStep.__table__.constraints
    )

    now = datetime.now(UTC)
    step = AcceptanceStep(
        id=uuid4(),
        phase_id=uuid4(),
        step_no=1,
        step_name="到货验收",
        responsible_id=uuid4(),
        plan_date=date(2026, 5, 20),
        description="check goods",
        status=AcceptanceStepStatus.not_started,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    payload = AcceptanceStepRead.model_validate(step).model_dump()
    assert payload["step_no"] == 1
    assert payload["status"] == AcceptanceStepStatus.not_started


@pytest.mark.asyncio
async def test_create_acceptance_step_requires_acceptance_phase_and_project_member() -> None:
    service, repository, leader, member, _sub_project, phase = make_service()

    step = await service.create_step(
        actor=leader,
        phase_id=phase.id,
        payload=AcceptanceStepCreate(
            step_no=1,
            step_name="到货验收",
            responsible_id=member.id,
            plan_date=date(2026, 5, 20),
            description="check goods",
        ),
    )

    assert step.step_no == 1
    assert step.status == AcceptanceStepStatus.not_started
    assert repository.acceptance_steps == [step]

    with pytest.raises(BusinessException) as exc_info:
        await service.create_step(
            actor=leader,
            phase_id=phase.id,
            payload=AcceptanceStepCreate(
                step_no=2,
                step_name="外部验收",
                responsible_id=uuid4(),
                plan_date=None,
                description=None,
            ),
        )
    assert exc_info.value.code == 3003


@pytest.mark.asyncio
async def test_complete_acceptance_step_requires_report_document() -> None:
    service, repository, leader, member, sub_project, phase = make_service()
    step = await service.create_step(
        actor=leader,
        phase_id=phase.id,
        payload=AcceptanceStepCreate(
            step_no=1,
            step_name="到货验收",
            responsible_id=member.id,
            plan_date=None,
            description=None,
        ),
    )

    with pytest.raises(BusinessException) as exc_info:
        await service.update_step(
            actor=member,
            phase_id=phase.id,
            step_id=step.id,
            payload=AcceptanceStepUpdate(status=AcceptanceStepStatus.completed),
        )
    assert exc_info.value.code == 3002

    repository.documents.append(make_document(sub_project, phase, step, member))
    completed = await service.update_step(
        actor=member,
        phase_id=phase.id,
        step_id=step.id,
        payload=AcceptanceStepUpdate(status=AcceptanceStepStatus.completed),
    )

    assert completed.status == AcceptanceStepStatus.completed
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_complete_acceptance_step_denies_unassigned_member() -> None:
    service, _repository, leader, member, _sub_project, phase = make_service()
    outsider = make_user(UserRole.proj_member, username="outsider")
    step = await service.create_step(
        actor=leader,
        phase_id=phase.id,
        payload=AcceptanceStepCreate(
            step_no=1,
            step_name="到货验收",
            responsible_id=member.id,
            plan_date=None,
            description=None,
        ),
    )

    with pytest.raises(PermissionDeniedError):
        await service.update_step(
            actor=outsider,
            phase_id=phase.id,
            step_id=step.id,
            payload=AcceptanceStepUpdate(status=AcceptanceStepStatus.in_progress),
        )


@pytest.mark.asyncio
async def test_phase_promote_requires_all_acceptance_steps_completed() -> None:
    service, repository, leader, member, sub_project, phase = make_service()
    phase1 = make_phase(sub_project, phase_no=1, status=PhaseStatus.completed)
    phase2 = make_phase(sub_project, phase_no=2, status=PhaseStatus.completed)
    phase3 = make_phase(sub_project, phase_no=3, status=PhaseStatus.completed)
    step = await service.create_step(
        actor=leader,
        phase_id=phase.id,
        payload=AcceptanceStepCreate(
            step_no=1,
            step_name="到货验收",
            responsible_id=member.id,
            plan_date=None,
            description=None,
        ),
    )
    phase_repository = InMemoryPhaseRepository(
        phases=[phase1, phase2, phase3, phase],
        phase_doc_templates=[
            PhaseDocTemplate(
                id=uuid4(),
                phase_no=4,
                doc_type="acceptance_report",
                requirement=PhaseDocRequirement.required,
                qty_rule=">=1",
                procurement_type=None,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ],
        documents=[],
        sub_projects=[sub_project],
        acceptance_steps=repository.acceptance_steps,
    )
    phase_service = PhaseService(repository=phase_repository)

    with pytest.raises(BusinessException) as exc_info:
        await phase_service.promote_phase(actor=leader, phase_id=phase.id)
    assert exc_info.value.code == 3003

    document = make_document(sub_project, phase, step, member)
    repository.documents.append(document)
    phase_repository.documents.append(document)
    await service.update_step(
        actor=member,
        phase_id=phase.id,
        step_id=step.id,
        payload=AcceptanceStepUpdate(status=AcceptanceStepStatus.completed),
    )
    result = await phase_service.promote_phase(actor=leader, phase_id=phase.id)

    assert result.phase.status == PhaseStatus.completed


def test_acceptance_step_endpoints_create_list_and_complete() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member = make_user(UserRole.proj_member, username="member")
    phase_id = uuid4()
    step = AcceptanceStep(
        id=uuid4(),
        phase_id=phase_id,
        step_no=1,
        step_name="到货验收",
        responsible_id=member.id,
        plan_date=None,
        description=None,
        status=AcceptanceStepStatus.completed,
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeAcceptanceStepService:
        async def list_steps(self, *, actor: User, phase_id: UUID) -> list[AcceptanceStep]:
            assert actor.id == leader.id
            assert phase_id == step.phase_id
            return [step]

        async def create_step(
            self,
            *,
            actor: User,
            phase_id: UUID,
            payload: AcceptanceStepCreate,
        ) -> AcceptanceStep:
            assert actor.id == leader.id
            assert phase_id == step.phase_id
            assert payload.responsible_id == member.id
            return step

        async def update_step(
            self,
            *,
            actor: User,
            phase_id: UUID,
            step_id: UUID,
            payload: AcceptanceStepUpdate,
        ) -> AcceptanceStep:
            assert actor.id == leader.id
            assert phase_id == step.phase_id
            assert step_id == step.id
            assert payload.status == AcceptanceStepStatus.completed
            return step

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return leader

    async def fake_service() -> FakeAcceptanceStepService:
        return FakeAcceptanceStepService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_acceptance_step_service] = fake_service
    client = TestClient(app)

    list_response = client.get(f"/api/v1/phases/{phase_id}/acceptance-steps")
    create_response = client.post(
        f"/api/v1/phases/{phase_id}/acceptance-steps",
        json={
            "description": None,
            "plan_date": None,
            "responsible_id": str(member.id),
            "step_name": "到货验收",
            "step_no": 1,
        },
    )
    update_response = client.put(
        f"/api/v1/phases/{phase_id}/acceptance-steps/{step.id}",
        json={"status": "completed"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == str(step.id)
    assert create_response.status_code == 200
    assert create_response.json()["data"]["step_no"] == 1
    assert update_response.status_code == 200
    assert update_response.json()["data"]["status"] == "completed"
