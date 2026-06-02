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
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.phases import (
    Phase,
    PhaseDocRequirement,
    PhaseDocTemplate,
    PhaseStatus,
    ProcurementType,
)
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.services.phases import InMemoryPhaseRepository, PhaseDetail, PhaseService


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


def make_phase(sub_project: SubProject, phase_no: int, status: PhaseStatus) -> Phase:
    now = datetime.now(UTC)
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=phase_no,
        code="procurement" if phase_no == 2 else "initiation",
        name="采购" if phase_no == 2 else "立项",
        status=status,
        enter_at=now if status == PhaseStatus.in_progress else None,
        finish_at=None,
        procurement_type=ProcurementType.bidding if phase_no == 2 else None,
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


@pytest.mark.asyncio
async def test_phase_service_lists_visible_phases_and_dynamic_required_documents() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    outsider = make_user(UserRole.proj_member, username="outsider")
    sub_project = make_sub_project(leader)
    initiation = make_phase(sub_project, 1, PhaseStatus.completed)
    procurement = make_phase(sub_project, 2, PhaseStatus.in_progress)
    repository = InMemoryPhaseRepository(
        phases=[initiation, procurement],
        phase_doc_templates=[
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
                "inquiry_report",
                PhaseDocRequirement.conditional,
                ">=1",
                ProcurementType.inquiry,
            ),
            make_template(2, "optional_note", PhaseDocRequirement.optional, "0-1"),
        ],
        sub_projects=[sub_project],
    )
    service = PhaseService(repository=repository)

    phases = await service.list_phases(actor=leader, sub_project_id=sub_project.id)
    detail = await service.get_phase(actor=leader, phase_id=procurement.id)

    assert [phase.id for phase in phases] == [initiation.id, procurement.id]
    assert [doc.doc_type for doc in detail.required_documents] == [
        "bid_document",
        "oa_screenshot",
    ]
    assert detail.completion.required_total == 2
    assert detail.completion.uploaded_total == 0
    assert detail.completion.missing_doc_types == ["bid_document", "oa_screenshot"]

    outsider_phases = await service.list_phases(actor=outsider, sub_project_id=sub_project.id)
    assert [phase.id for phase in outsider_phases] == [initiation.id, procurement.id]


def test_phase_query_endpoints_return_required_documents() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    sub_project = make_sub_project(leader)
    procurement = make_phase(sub_project, 2, PhaseStatus.in_progress)
    required_template = make_template(
        2,
        "bid_document",
        PhaseDocRequirement.conditional,
        "=1",
        ProcurementType.bidding,
    )

    class FakePhaseService:
        async def list_phases(self, *, actor: User, sub_project_id: UUID) -> list[Phase]:
            assert actor.id == leader.id
            assert sub_project_id == sub_project.id
            return [procurement]

        async def get_phase(self, *, actor: User, phase_id: UUID) -> PhaseDetail:
            assert actor.id == leader.id
            assert phase_id == procurement.id
            return PhaseDetail.from_required_documents(
                phase=procurement,
                required_documents=[required_template],
            )

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

    list_response = client.get(f"/api/v1/phases?sub_project_id={sub_project.id}")
    detail_response = client.get(f"/api/v1/phases/{procurement.id}")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == str(procurement.id)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["data"]
    assert detail_payload["required_documents"][0]["doc_type"] == "bid_document"
    assert detail_payload["uploaded_documents"] == []
    assert detail_payload["completion"]["missing_doc_types"] == ["bid_document"]
