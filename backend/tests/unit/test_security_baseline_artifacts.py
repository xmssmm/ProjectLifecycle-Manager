from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = REPO_ROOT / "docs" / "security-baseline.md"


def test_security_baseline_report_covers_required_checks_and_evidence() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "T-1-TEST-05" in report
    for check in (
        "pip-audit",
        "npm audit",
        "越权测试",
        "弱密码测试",
        "JWT 篡改 / 过期 / 黑名单",
        "SQL 注入",
    ):
        assert check in report
    for outcome in ("高危漏洞", "测试证据", "处理结论"):
        assert outcome in report
    for artifact in ("security-pip-audit.json", "security-npm-audit.json"):
        assert (REPO_ROOT / "docs" / artifact).exists()
