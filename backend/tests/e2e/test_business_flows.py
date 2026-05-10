from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.models.documents import Document
from app.models.main_projects import (
    MainProject,
    MainProjectStatus,
    ProjectReview,
    ProjectReviewDecision,
)
from app.models.notifications import Notification
from app.models.payments import PaymentType
from app.models.phases import Phase, PhaseStatus
from app.models.revoke_requests import RevokeRequestStatus, RevokeReviewDecision
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.schemas.main_projects import MainProjectCreate, MainProjectReviewRequest
from app.schemas.revoke_requests import RevokeRequestCreate, RevokeRequestReview
from app.schemas.sub_projects import (
    SubProjectBatchHandoverItem,
    SubProjectCreate,
    SubProjectMemberCreate,
    SubProjectReviewRequest,
)
from app.services.audit import AuditContext
from app.services.documents import DocumentService, SqlAlchemyDocumentRepository
from app.services.payments import PaymentVoucherUpload
from tests.e2e.conftest import E2EContext

PDF_BYTES = b"%PDF-1.7\n% e2e fixture\n"


@pytest.mark.asyncio
async def test_full_project_lifecycle_e2e_uses_fresh_database(
    e2e_context: E2EContext,
) -> None:
    main_project, sub_project = await _create_approved_project_tree(e2e_context)
    await e2e_context.sub_projects().add_sub_project_member(
        actor=e2e_context.leader,
        sub_project_id=sub_project.id,
        payload=SubProjectMemberCreate(user_id=e2e_context.member.id),
    )
    phases = await _phases_by_no(e2e_context, sub_project.id)

    await _upload_required_documents(e2e_context, sub_project, phases[1], "meeting_material")
    await _upload_required_documents(e2e_context, sub_project, phases[1], "meeting_minutes")
    result = await e2e_context.phases().promote_phase(
        actor=e2e_context.leader,
        phase_id=phases[1].id,
    )
    assert result.activated_phase is not None
    assert result.activated_phase.phase_no == 2

    phases = await _phases_by_no(e2e_context, sub_project.id)
    await _upload_required_documents(e2e_context, sub_project, phases[2], "oa_screenshot")
    await e2e_context.phases().promote_phase(actor=e2e_context.leader, phase_id=phases[2].id)

    phases = await _phases_by_no(e2e_context, sub_project.id)
    await _upload_required_documents(e2e_context, sub_project, phases[3], "contract")
    await e2e_context.phases().promote_phase(actor=e2e_context.leader, phase_id=phases[3].id)

    phases = await _phases_by_no(e2e_context, sub_project.id)
    await _upload_required_documents(e2e_context, sub_project, phases[4], "acceptance_report")
    await e2e_context.phases().promote_phase(actor=e2e_context.leader, phase_id=phases[4].id)

    phases = await _phases_by_no(e2e_context, sub_project.id)
    await _upload_required_documents(e2e_context, sub_project, phases[6], "post_review_report")
    await _upload_required_documents(
        e2e_context,
        sub_project,
        phases[6],
        "economic_benefit_report",
    )
    await e2e_context.phases().promote_phase(actor=e2e_context.leader, phase_id=phases[6].id)

    first_payment = await e2e_context.payments().create_payment(
        actor=e2e_context.finance,
        sub_project_id=sub_project.id,
        amount=Decimal("120.50"),
        payment_date=date(2026, 5, 10),
        remark="first payment",
        voucher_files=[_voucher("voucher-1.pdf")],
    )
    second_payment = await e2e_context.payments().create_payment(
        actor=e2e_context.finance,
        sub_project_id=sub_project.id,
        amount=Decimal("79.50"),
        payment_date=date(2026, 5, 11),
        remark="second payment",
        voucher_files=[_voucher("voucher-2.pdf")],
    )
    phases = await _phases_by_no(e2e_context, sub_project.id)
    await e2e_context.phases().promote_phase(actor=e2e_context.leader, phase_id=phases[5].id)

    closed_sub_project = await e2e_context.sub_projects().close_sub_project(
        actor=e2e_context.dept_manager,
        sub_project_id=sub_project.id,
    )
    closed_main_project = await e2e_context.main_projects().close_project(
        actor=e2e_context.dept_manager,
        project_id=main_project.id,
    )

    assert first_payment.payment_no.endswith("PAY-001")
    assert second_payment.payment_no.endswith("PAY-002")
    assert closed_sub_project.status == SubProjectStatus.closed
    assert closed_main_project.status == MainProjectStatus.closed
    assert closed_sub_project.spent_amount == Decimal("200.00")
    assert closed_main_project.spent_amount == Decimal("200.00")


@pytest.mark.asyncio
async def test_revoke_completed_phase_soft_deletes_documents_and_notifies(
    e2e_context: E2EContext,
) -> None:
    _main_project, sub_project = await _create_approved_project_tree(e2e_context)
    phases = await _complete_first_three_phases(e2e_context, sub_project)
    phase3_document = await _latest_document(e2e_context, phases[3].id, "contract")

    request = await e2e_context.revoke_requests().submit_request(
        actor=e2e_context.leader,
        payload=RevokeRequestCreate(phase_id=phases[3].id, reason="contract correction"),
    )
    reviewed = await e2e_context.revoke_requests().review_request(
        actor=e2e_context.dept_manager,
        request_id=request.id,
        payload=RevokeRequestReview(
            decision=RevokeReviewDecision.approve,
            review_comment="approved",
        ),
        audit_writer=e2e_context.audit_writer,
        audit_context=AuditContext(actor_id=e2e_context.dept_manager.id),
    )
    await e2e_context.session.refresh(phase3_document)
    refreshed_phases = await _phases_by_no(e2e_context, sub_project.id)
    scenarios = await _notification_scenarios(e2e_context)

    assert reviewed.status == RevokeRequestStatus.approved
    assert phase3_document.is_deleted is True
    assert refreshed_phases[3].status == PhaseStatus.in_progress
    assert refreshed_phases[4].status == PhaseStatus.waiting
    assert {"revoke_request_pending", "revoke_result"}.issubset(scenarios)
    assert e2e_context.audit_writer.entries[-1].action == "revoke_request.review"


@pytest.mark.asyncio
async def test_payment_reversal_flow_keeps_spent_amount_accurate(
    e2e_context: E2EContext,
) -> None:
    main_project, sub_project = await _create_approved_project_tree(e2e_context)
    original = await e2e_context.payments().create_payment(
        actor=e2e_context.finance,
        sub_project_id=sub_project.id,
        amount=Decimal("350.00"),
        payment_date=date(2026, 5, 10),
        remark="wrong amount",
        voucher_files=[_voucher("wrong-voucher.pdf")],
    )

    reversal = await e2e_context.payments().reverse_payment(
        actor=e2e_context.finance,
        sub_project_id=sub_project.id,
        reverses_payment_id=original.id,
        remark="reverse wrong amount",
    )
    await e2e_context.session.refresh(sub_project)
    await e2e_context.session.refresh(main_project)

    assert reversal.payment_type == PaymentType.reversal
    assert reversal.amount == Decimal("-350.00")
    assert sub_project.spent_amount == Decimal("0.00")
    assert main_project.spent_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_admin_batch_handover_sends_notifications_and_audit_entries(
    e2e_context: E2EContext,
) -> None:
    _main_project, first = await _create_approved_project_tree(e2e_context, name_suffix="A")
    _second_main, second = await _create_approved_project_tree(e2e_context, name_suffix="B")
    service = e2e_context.sub_projects()

    handed_over = await service.batch_handover_sub_projects(
        actor=e2e_context.admin,
        from_user_id=e2e_context.leader.id,
        payload=[
            SubProjectBatchHandoverItem(
                sub_project_id=first.id,
                to_user_id=e2e_context.new_leader.id,
                reason="leader changed",
            ),
            SubProjectBatchHandoverItem(
                sub_project_id=second.id,
                to_user_id=e2e_context.new_leader.id,
                reason="leader changed",
            ),
        ],
        audit_writer=e2e_context.audit_writer,
        audit_context=AuditContext(actor_id=e2e_context.admin.id),
    )
    member_roles = await _member_roles(e2e_context, first.id)
    scenarios = await _notification_scenarios(e2e_context)

    assert [item.manager_id for item in handed_over] == [
        e2e_context.new_leader.id,
        e2e_context.new_leader.id,
    ]
    assert member_roles[e2e_context.leader.id] == SubProjectMemberRole.proj_member
    assert member_roles[e2e_context.new_leader.id] == SubProjectMemberRole.proj_leader
    assert scenarios.count("handover_completed") >= 2
    assert [entry.action for entry in e2e_context.audit_writer.entries] == [
        "sub_project.handover",
        "sub_project.handover",
    ]


@pytest.mark.asyncio
async def test_single_dept_manager_deadlock_uses_admin_override_review(
    e2e_context: E2EContext,
) -> None:
    project = await e2e_context.main_projects().create_project(
        actor=e2e_context.dept_manager,
        payload=MainProjectCreate(
            name="Deadlock main project",
            dept_id=e2e_context.department.id,
            total_budget=Decimal("10000.00"),
            expected_finish_date=date(2026, 12, 31),
            remark=None,
        ),
    )

    approved = await e2e_context.main_projects().review_project(
        actor=e2e_context.admin,
        project_id=project.id,
        payload=MainProjectReviewRequest(
            decision=ProjectReviewDecision.approve,
            review_comment="admin fallback",
        ),
        audit_writer=e2e_context.audit_writer,
        audit_context=AuditContext(actor_id=e2e_context.admin.id),
    )
    review = await e2e_context.session.scalar(
        select(ProjectReview).where(ProjectReview.main_project_id == project.id),
    )

    assert approved.status == MainProjectStatus.not_started
    assert review is not None
    assert review.admin_override is True
    assert e2e_context.audit_writer.entries[-1].extra["admin_override"] is True


@pytest.mark.asyncio
async def test_concurrent_same_doc_type_uploads_assign_unique_versions(
    e2e_context: E2EContext,
) -> None:
    _main_project, sub_project = await _create_approved_project_tree(e2e_context)
    phase = (await _phases_by_no(e2e_context, sub_project.id))[1]
    await _upload_required_documents(e2e_context, sub_project, phase, "meeting_material")
    engine = cast(AsyncEngine, e2e_context.session.bind)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def upload_copy(index: int) -> None:
        async with session_factory() as session:
            service = DocumentService(
                repository=SqlAlchemyDocumentRepository(session),
                storage=e2e_context.storage,
                max_file_size_bytes=1024 * 1024,
            )
            await service.upload_document(
                actor=e2e_context.leader,
                sub_project_id=sub_project.id,
                phase_id=phase.id,
                doc_type="meeting_material",
                file_name=f"meeting-material-{index}.pdf",
                content_type="application/pdf",
                content=PDF_BYTES,
            )

    await asyncio.gather(*(upload_copy(index) for index in range(2, 8)))
    documents = list(
        await e2e_context.session.scalars(
            select(Document)
            .where(
                Document.sub_project_id == sub_project.id,
                Document.phase_id == phase.id,
                Document.doc_type == "meeting_material",
            )
            .order_by(Document.version),
        ),
    )

    assert [document.version for document in documents] == list(range(1, 8))
    assert [document.version for document in documents if document.is_latest] == [7]


async def _create_approved_project_tree(
    context: E2EContext,
    *,
    name_suffix: str = "",
) -> tuple[MainProject, SubProject]:
    main_project = await context.main_projects().create_project(
        actor=context.dept_manager,
        payload=MainProjectCreate(
            name=f"Main Project {name_suffix}".strip(),
            dept_id=context.department.id,
            total_budget=Decimal("10000.00"),
            expected_finish_date=date(2026, 12, 31),
            remark="e2e",
        ),
    )
    await context.main_projects().review_project(
        actor=context.admin,
        project_id=main_project.id,
        payload=MainProjectReviewRequest(
            decision=ProjectReviewDecision.approve,
            review_comment="approved",
        ),
    )
    sub_project = await context.sub_projects().create_sub_project(
        actor=context.leader,
        payload=SubProjectCreate(
            name=f"Sub Project {name_suffix}".strip(),
            main_project_id=main_project.id,
            dept_id=context.department.id,
            budget=Decimal("1000.00"),
            plan_end_date=date(2026, 10, 31),
            remark="e2e",
        ),
    )
    await context.sub_projects().review_sub_project(
        actor=context.dept_manager,
        sub_project_id=sub_project.id,
        payload=SubProjectReviewRequest(
            decision=ProjectReviewDecision.approve,
            review_comment="approved",
        ),
    )
    await context.session.refresh(main_project)
    await context.session.refresh(sub_project)
    return main_project, sub_project


async def _complete_first_three_phases(
    context: E2EContext,
    sub_project: SubProject,
) -> dict[int, Phase]:
    phases = await _phases_by_no(context, sub_project.id)
    await _upload_required_documents(context, sub_project, phases[1], "meeting_material")
    await _upload_required_documents(context, sub_project, phases[1], "meeting_minutes")
    await context.phases().promote_phase(actor=context.leader, phase_id=phases[1].id)
    phases = await _phases_by_no(context, sub_project.id)
    await _upload_required_documents(context, sub_project, phases[2], "oa_screenshot")
    await context.phases().promote_phase(actor=context.leader, phase_id=phases[2].id)
    phases = await _phases_by_no(context, sub_project.id)
    await _upload_required_documents(context, sub_project, phases[3], "contract")
    await context.phases().promote_phase(actor=context.leader, phase_id=phases[3].id)
    return await _phases_by_no(context, sub_project.id)


async def _upload_required_documents(
    context: E2EContext,
    sub_project: SubProject,
    phase: Phase,
    doc_type: str,
) -> Document:
    return await context.documents().upload_document(
        actor=context.leader,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type=doc_type,
        file_name=f"{doc_type}.pdf",
        content_type="application/pdf",
        content=PDF_BYTES,
    )


def _voucher(file_name: str) -> PaymentVoucherUpload:
    return PaymentVoucherUpload(
        file_name=file_name,
        content_type="application/pdf",
        content=PDF_BYTES,
    )


async def _phases_by_no(context: E2EContext, sub_project_id: UUID) -> dict[int, Phase]:
    phases = await context.session.scalars(
        select(Phase).where(Phase.sub_project_id == sub_project_id).order_by(Phase.phase_no),
    )
    return {phase.phase_no: phase for phase in phases}


async def _latest_document(context: E2EContext, phase_id: UUID, doc_type: str) -> Document:
    document = await context.session.scalar(
        select(Document).where(
            Document.phase_id == phase_id,
            Document.doc_type == doc_type,
            Document.is_latest.is_(True),
        ),
    )
    assert document is not None
    return document


async def _notification_scenarios(context: E2EContext) -> list[str]:
    notifications = await context.session.scalars(
        select(Notification).order_by(Notification.created_at, Notification.scenario),
    )
    return [notification.scenario for notification in notifications]


async def _member_roles(
    context: E2EContext,
    sub_project_id: UUID,
) -> dict[UUID, SubProjectMemberRole]:
    members = await context.session.scalars(
        select(SubProjectMember).where(SubProjectMember.sub_project_id == sub_project_id),
    )
    return {member.user_id: member.role_in_project for member in members}
