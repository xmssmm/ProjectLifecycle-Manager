from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCUSTFILE_PATH = REPO_ROOT / "backend" / "perf" / "locustfile.py"
REPORT_PATH = REPO_ROOT / "docs" / "perf-baseline.md"


def test_locustfile_covers_required_50_user_business_flows() -> None:
    source = LOCUSTFILE_PATH.read_text(encoding="utf-8")

    assert "class ManagementApiLoadUser(HttpUser)" in source
    assert "PROMOTE_POOL_SIZE" in source
    for endpoint in (
        "/auth/login",
        "/main-projects",
        "/documents",
        "/phases/{phase_id}/promote",
        "/sub-projects/{self.data['sub_project_id']}/payments",
    ):
        assert endpoint in source


def test_perf_baseline_report_records_sla_result_and_fix_list() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "T-1-TEST-04" in report
    assert "50 并发" in report
    assert "P99 <= 800ms" in report
    assert "fix 清单" in report
    assert "待测" not in report
    for operation in ("登录", "查项目列表", "上传文档", "推进环节", "新增付款"):
        assert operation in report
    for suffix in ("stats", "failures", "exceptions", "stats_history"):
        assert (REPO_ROOT / "docs" / f"perf-baseline_{suffix}.csv").exists()
