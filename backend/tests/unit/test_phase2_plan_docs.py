from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_phase2_plan_records_scope_order_and_default_decisions() -> None:
    plan = (ROOT_DIR / "docs" / "PHASE_2_PLAN.md").read_text(encoding="utf-8")
    questions = (ROOT_DIR / "docs" / "PHASE_2_OPEN_QUESTIONS.md").read_text(encoding="utf-8")

    for task_id in (
        "T-2-DASH-01",
        "T-2-DASH-02",
        "T-2-REPORT-01",
        "T-2-MOBILE-01",
        "T-2-DOC-04",
        "T-2-NOTIF-04",
    ):
        assert task_id in plan

    assert "仪表盘数据缓存 5 分钟" in questions
    assert "不做电子签章" in questions
    assert "LibreOffice 转 PDF" in questions
    assert "自动继续执行" in questions
