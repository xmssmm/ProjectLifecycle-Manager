from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / "docs" / "rule-failure-test-matrix.md"
REQUIRED_RULE_IDS = tuple(f"KR-{index:02d}" for index in range(1, 15))
TEST_NODE_PATTERN = re.compile(
    r"`(?P<node>backend/tests/[^`|]+?::[A-Za-z_][A-Za-z0-9_]*)`"
)


def _read_matrix() -> str:
    return MATRIX_PATH.read_text(encoding="utf-8")


def _extract_rule_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\|\s*(KR-\d{2})\s*\|", line)
        if match is not None:
            rows[match.group(1)] = line
    return rows


def _assert_test_node_exists(node: str) -> None:
    path_part, test_name = node.split("::", 1)
    test_file = REPO_ROOT / path_part
    assert test_file.exists(), f"{node} references a missing test file"
    source = test_file.read_text(encoding="utf-8")
    pattern = rf"^\s*(async\s+)?def\s+{re.escape(test_name)}\b"
    assert re.search(pattern, source, re.MULTILINE), f"{node} references a missing test"


def test_key_rule_matrix_lists_all_required_scenarios_once() -> None:
    rows = _extract_rule_rows(_read_matrix())

    assert tuple(rows) == REQUIRED_RULE_IDS


def test_key_rule_matrix_links_existing_failure_path_tests() -> None:
    rows = _extract_rule_rows(_read_matrix())

    for rule_id in REQUIRED_RULE_IDS:
        row = rows[rule_id]
        nodes = TEST_NODE_PATTERN.findall(row)
        assert nodes, f"{rule_id} must link at least one concrete test node"
        for node in nodes:
            _assert_test_node_exists(node)
