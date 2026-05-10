from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.phases import PhaseDocRequirement, PhaseDocTemplate, ProcurementType


@dataclass(frozen=True)
class PhaseDocTemplateSeed:
    phase_no: int
    doc_type: str
    requirement: PhaseDocRequirement
    qty_rule: str
    procurement_type: ProcurementType | None = None


PHASE_DOC_TEMPLATES = (
    PhaseDocTemplateSeed(1, "meeting_material", PhaseDocRequirement.required, "=1"),
    PhaseDocTemplateSeed(1, "meeting_minutes", PhaseDocRequirement.required, "=1"),
    PhaseDocTemplateSeed(2, "oa_screenshot", PhaseDocRequirement.required, "=1"),
    PhaseDocTemplateSeed(
        2,
        "inquiry_report",
        PhaseDocRequirement.conditional,
        ">=1",
        ProcurementType.inquiry,
    ),
    PhaseDocTemplateSeed(
        2,
        "bid_announcement",
        PhaseDocRequirement.conditional,
        "=1",
        ProcurementType.bidding,
    ),
    PhaseDocTemplateSeed(
        2,
        "bid_document",
        PhaseDocRequirement.conditional,
        "=1",
        ProcurementType.bidding,
    ),
    PhaseDocTemplateSeed(
        2,
        "bid_result",
        PhaseDocRequirement.conditional,
        "=1",
        ProcurementType.bidding,
    ),
    PhaseDocTemplateSeed(
        2,
        "single_source_report",
        PhaseDocRequirement.conditional,
        "=1",
        ProcurementType.single_source,
    ),
    PhaseDocTemplateSeed(
        2,
        "negotiation_report",
        PhaseDocRequirement.conditional,
        "=1",
        ProcurementType.single_source,
    ),
    PhaseDocTemplateSeed(3, "contract", PhaseDocRequirement.required, "=1"),
    PhaseDocTemplateSeed(3, "supplementary_contract", PhaseDocRequirement.optional, "0-1"),
    PhaseDocTemplateSeed(4, "acceptance_report", PhaseDocRequirement.required, ">=1"),
    PhaseDocTemplateSeed(5, "payment_voucher", PhaseDocRequirement.required, "per_payment>=1"),
    PhaseDocTemplateSeed(6, "post_review_report", PhaseDocRequirement.required, "=1"),
    PhaseDocTemplateSeed(6, "economic_benefit_report", PhaseDocRequirement.required, "=1"),
)


async def seed_phase_doc_templates(session: AsyncSession) -> int:
    inserted = 0
    for template in PHASE_DOC_TEMPLATES:
        stmt = select(PhaseDocTemplate.id).where(
            PhaseDocTemplate.phase_no == template.phase_no,
            PhaseDocTemplate.doc_type == template.doc_type,
        )
        if template.procurement_type is None:
            stmt = stmt.where(PhaseDocTemplate.procurement_type.is_(None))
        else:
            stmt = stmt.where(PhaseDocTemplate.procurement_type == template.procurement_type)
        existing = await session.scalar(stmt)
        if existing is not None:
            continue
        session.add(
            PhaseDocTemplate(
                phase_no=template.phase_no,
                doc_type=template.doc_type,
                requirement=template.requirement,
                qty_rule=template.qty_rule,
                procurement_type=template.procurement_type,
                is_active=True,
            ),
        )
        inserted += 1
    return inserted
