from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.phases import get_phase_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.documents import Document
from app.models.phases import (
    Phase,
    PhaseDocRequirement,
    PhaseDocTemplate,
    PhaseStatus,
    ProcurementType,
)
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.models.workflows import WorkflowTemplateStatus, WorkflowTemplateVersion
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.phases import InMemoryPhaseRepository, PhasePromotionResult, PhaseService


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


def make_workflow_version() -> WorkflowTemplateVersion:
    now = datetime.now(UTC)
    return WorkflowTemplateVersion(
        id=uuid4(),
        template_id=uuid4(),
        version_no=1,
        status=WorkflowTemplateStatus.published,
        phase_definitions=[
            {
                "key": "proposal",
                "name": "课题申报",
                "order": 1,
                "required_documents": [
                    {
                        "doc_type": "proposal_doc",
                        "requirement": "required",
                        "qty_rule": "=1",
                        "procurement_type": None,
                    },
                ],
                "allow_parallel": False,
                "entry_rules": {},
            },
        ],
        published_at=now,
        created_at=now,
        updated_at=now,
    )


def make_phase(
    sub_project: SubProject,
    phase_no: int,
    status: PhaseStatus,
    *,
    procurement_type: ProcurementType | None = None,
) -> Phase:
    now = datetime.now(UTC)
    names = {
        1: ("initiation", "立项"),
        2: ("procurement", "采购"),
        3: ("contract", "合同"),
        4: ("acceptance", "验收"),
        5: ("payment", "付款"),
        6: ("post_review", "后评价"),
    }
    code, name = names[phase_no]
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=phase_no,
        code=code,
        name=name,
        status=status,
        enter_at=now if status == PhaseStatus.in_progress else None,
        finish_at=None,
        procurement_type=procurement_type,
        created_at=now,
        updated_at=now,
    )


def make_template(
    phase_no: int,
    doc_type: str,
    requirement: PhaseDocRequirement,
    qty_rule: str,
    procurement_type: ProcurementType | None = None,
) -> PhaseDocTemplate:
    now = datetime.now(UTC)
    return PhaseDocTemplate(
        id=uuid4(),
        phase_no=phase_no,
        doc_type=doc_type,
        requirement=requirement,
        qty_rule=qty_rule,
        procurement_type=procurement_type,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_document(
    *,
    sub_project: SubProject,
    phase: Phase,
    uploader: User,
    doc_type: str,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        acceptance_step_id=None,
        doc_type=doc_type,
        file_name=f"{doc_type}.pdf",
        file_path=f"{sub_project.id}/{phase.id}/{doc_type}.pdf",
        file_size=128,
        version=1,
        is_latest=True,
        is_deleted=False,
        uploader_id=uploader.id,
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


def make_service(
    *,
    sub_projects: list[SubProject],
    phases: list[Phase],
    templates: list[PhaseDocTemplate],
    documents: list[Document] | None = None,
    members: list[SubProjectMember] | None = None,
    workflow_versions: list[WorkflowTemplateVersion] | None = None,
) -> tuple[PhaseService, InMemoryPhaseRepository, InMemoryNotificationRepository]:
    repository = InMemoryPhaseRepository(
        phases=phases,
        phase_doc_templates=templates,
        documents=documents or [],
        sub_projects=sub_projects,
        members=members or [],
        workflow_versions=workflow_versions or [],
    )
    notification_repository = InMemoryNotificationRepository()
    service = PhaseService(
        repository=repository,
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: date(2026, 5, 10),
        ),
        today_provider=lambda: date(2026, 5, 10),
    )
    return service, repository, notification_repository


@pytest.mark.asyncio
async def test_promote_phase_rejects_missing_conditional_documents() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase1 = make_phase(sub_project, 1, PhaseStatus.completed)
    phase2 = make_phase(
        sub_project,
        2,
        PhaseStatus.in_progress,
        procurement_type=ProcurementType.bidding,
    )
    service, _repository, _notifications = make_service(
        sub_projects=[sub_project],
        phases=[phase1, phase2],
        templates=[
            make_template(2, "oa_screenshot", PhaseDocRequirement.required, "=1"),
            make_template(
                2,
                "bid_document",
                PhaseDocRequirement.conditional,
                "=1",
                ProcurementType.bidding,
            ),
            make_template(
                2,
                "single_source_report",
                PhaseDocRequirement.conditional,
                "=1",
                ProcurementType.single_source,
            ),
        ],
        documents=[
            make_document(
                sub_project=sub_project,
                phase=phase2,
                uploader=leader,
                doc_type="oa_screenshot",
            ),
        ],
    )

    with pytest.raises(BusinessException) as exc:
        await service.promote_phase(actor=leader, phase_id=phase2.id)

    assert exc.value.code == 3002
    assert exc.value.data == {
        "missing_documents": [
            {"doc_type": "bid_document", "required": "=1", "actual": 0},
        ],
    }


@pytest.mark.asyncio
async def test_promote_phase_uses_workflow_template_required_documents() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    workflow_version = make_workflow_version()
    sub_project = make_sub_project(leader)
    sub_project.workflow_template_version_id = workflow_version.id
    phase = Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=1,
        code="proposal",
        name="课题申报",
        status=PhaseStatus.in_progress,
        enter_at=datetime.now(UTC),
        finish_at=None,
        procurement_type=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service, _repository, _notifications = make_service(
        sub_projects=[sub_project],
        phases=[phase],
        templates=[],
        workflow_versions=[workflow_version],
    )

    with pytest.raises(BusinessException) as exc:
        await service.promote_phase(actor=leader, phase_id=phase.id)

    assert exc.value.code == 3002
    assert exc.value.data == {
        "missing_documents": [
            {"doc_type": "proposal_doc", "required": "=1", "actual": 0},
        ],
    }


@pytest.mark.asyncio
async def test_promote_phase_uses_assigned_workflow_version_snapshot() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    legacy_version = make_workflow_version()
    newer_version = make_workflow_version()
    newer_version.template_id = legacy_version.template_id
    newer_version.version_no = 2
    newer_version.phase_definitions[0]["required_documents"] = [
        {
            "doc_type": "new_policy_doc",
            "requirement": "required",
            "qty_rule": "=1",
            "procurement_type": None,
        },
    ]
    sub_project = make_sub_project(leader)
    sub_project.workflow_template_version_id = legacy_version.id
    phase = Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=1,
        code="proposal",
        name="Proposal",
        status=PhaseStatus.in_progress,
        enter_at=datetime.now(UTC),
        finish_at=None,
        procurement_type=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service, _repository, _notifications = make_service(
        sub_projects=[sub_project],
        phases=[phase],
        templates=[],
        workflow_versions=[newer_version, legacy_version],
    )

    with pytest.raises(BusinessException) as exc:
        await service.promote_phase(actor=leader, phase_id=phase.id)

    assert exc.value.code == 3002
    assert exc.value.data == {
        "missing_documents": [
            {"doc_type": "proposal_doc", "required": "=1", "actual": 0},
        ],
    }


@pytest.mark.asyncio
async def test_promote_phase_completes_current_activates_next_and_notifies_members() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member = make_user(UserRole.proj_member, username="member")
    sub_project = make_sub_project(leader)
    phase1 = make_phase(sub_project, 1, PhaseStatus.in_progress)
    phase2 = make_phase(sub_project, 2, PhaseStatus.waiting)
    service, repository, notifications = make_service(
        sub_projects=[sub_project],
        phases=[phase1, phase2],
        templates=[
            make_template(1, "meeting_material", PhaseDocRequirement.required, "=1"),
            make_template(1, "meeting_minutes", PhaseDocRequirement.required, "=1"),
        ],
        documents=[
            make_document(
                sub_project=sub_project,
                phase=phase1,
                uploader=leader,
                doc_type="meeting_material",
            ),
            make_document(
                sub_project=sub_project,
                phase=phase1,
                uploader=leader,
                doc_type="meeting_minutes",
            ),
        ],
        members=[make_member(sub_project, leader), make_member(sub_project, member)],
    )

    result = await service.promote_phase(actor=leader, phase_id=phase1.id)

    assert result.phase.id == phase1.id
    assert result.activated_phase is not None
    assert result.activated_phase.id == phase2.id
    assert phase1.status == PhaseStatus.completed
    assert phase1.finish_at is not None
    assert phase2.status == PhaseStatus.in_progress
    assert phase2.enter_at is not None
    assert repository.histories[0].phase_id == phase1.id
    assert repository.histories[0].from_status == PhaseStatus.in_progress
    assert repository.histories[0].to_status == PhaseStatus.completed
    assert {notification.receiver_id for notification in notifications.notifications} == {
        leader.id,
        member.id,
    }
    assert notifications.notifications[0].scenario == "phase_promoted"


@pytest.mark.asyncio
async def test_promote_post_review_requires_acceptance_completed() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase4 = make_phase(sub_project, 4, PhaseStatus.in_progress)
    phase6 = make_phase(sub_project, 6, PhaseStatus.in_progress)
    service, _repository, _notifications = make_service(
        sub_projects=[sub_project],
        phases=[phase4, phase6],
        templates=[
            make_template(6, "post_review_report", PhaseDocRequirement.required, "=1"),
            make_template(6, "economic_benefit_report", PhaseDocRequirement.required, "=1"),
        ],
        documents=[
            make_document(
                sub_project=sub_project,
                phase=phase6,
                uploader=leader,
                doc_type="post_review_report",
            ),
            make_document(
                sub_project=sub_project,
                phase=phase6,
                uploader=leader,
                doc_type="economic_benefit_report",
            ),
        ],
    )

    with pytest.raises(BusinessException) as exc:
        await service.promote_phase(actor=leader, phase_id=phase6.id)

    assert exc.value.code == 3003
    assert phase6.status == PhaseStatus.in_progress


@pytest.mark.asyncio
async def test_promote_phase_denies_non_leader_project_member() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member = make_user(UserRole.proj_member, username="member")
    sub_project = make_sub_project(leader)
    phase1 = make_phase(sub_project, 1, PhaseStatus.in_progress)
    service, _repository, _notifications = make_service(
        sub_projects=[sub_project],
        phases=[phase1],
        templates=[],
        members=[make_member(sub_project, member)],
    )

    with pytest.raises(PermissionDeniedError):
        await service.promote_phase(actor=member, phase_id=phase1.id)


def test_phase_promote_endpoint_returns_current_and_activated_phase() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    phase1 = make_phase(sub_project, 1, PhaseStatus.completed)
    phase2 = make_phase(sub_project, 2, PhaseStatus.in_progress)

    class FakePhaseService:
        async def promote_phase(self, *, actor: User, phase_id: UUID) -> PhasePromotionResult:
            assert actor.id == leader.id
            assert phase_id == phase1.id
            return PhasePromotionResult(phase=phase1, activated_phase=phase2)

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return leader

    async def fake_phase_service() -> FakePhaseService:
        return FakePhaseService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_phase_service] = fake_phase_service
    client = TestClient(app)

    response = client.post(f"/api/v1/phases/{phase1.id}/promote")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["phase"]["id"] == str(phase1.id)
    assert payload["activated_phase"]["id"] == str(phase2.id)
