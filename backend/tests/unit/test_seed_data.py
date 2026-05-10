from __future__ import annotations

import pytest

from app.models.phases import PhaseDocRequirement, ProcurementType
from app.seeds.default_admin import get_default_admin_credentials
from app.seeds.default_departments import DEFAULT_DEPARTMENTS
from app.seeds.phase_doc_templates import PHASE_DOC_TEMPLATES


def test_default_admin_credentials_are_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", "root")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "RootPass1!")

    credentials = get_default_admin_credentials()

    assert credentials.username == "root"
    assert credentials.password == "RootPass1!"


def test_default_admin_credentials_reject_blank_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", " ")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "RootPass1!")

    with pytest.raises(ValueError, match="DEFAULT_ADMIN_USERNAME"):
        get_default_admin_credentials()


def test_default_department_seed_data_has_required_departments() -> None:
    departments = {department.code: department.name for department in DEFAULT_DEPARTMENTS}

    assert departments == {
        "general": "\u7efc\u5408\u90e8",
        "finance": "\u8d22\u52a1\u90e8",
        "business": "\u4e1a\u52a1\u90e8",
    }


def test_phase_doc_template_seed_data_matches_requirements_section_3_2() -> None:
    assert len(PHASE_DOC_TEMPLATES) == 15

    rows = {
        (template.phase_no, template.doc_type, template.procurement_type): template
        for template in PHASE_DOC_TEMPLATES
    }

    assert rows[(1, "meeting_material", None)].requirement == PhaseDocRequirement.required
    assert rows[(2, "oa_screenshot", None)].qty_rule == "=1"
    assert rows[(2, "inquiry_report", ProcurementType.inquiry)].qty_rule == ">=1"
    assert rows[(2, "bid_document", ProcurementType.bidding)].requirement == (
        PhaseDocRequirement.conditional
    )
    assert rows[(2, "single_source_report", ProcurementType.single_source)].qty_rule == "=1"
    assert rows[(3, "supplementary_contract", None)].requirement == PhaseDocRequirement.optional
    assert rows[(5, "payment_voucher", None)].qty_rule == "per_payment>=1"
