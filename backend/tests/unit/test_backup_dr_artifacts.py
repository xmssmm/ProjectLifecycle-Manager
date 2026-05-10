from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_backup_script_covers_database_storage_and_oss_placeholder() -> None:
    script = (ROOT_DIR / "scripts" / "backup.sh").read_text(encoding="utf-8")

    assert script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in script
    assert "pg_dump" in script
    assert "BACKUP_DB_MODE" in script
    assert "docker compose" in script
    assert "--file=-" not in script
    assert "storage.tar.gz" in script
    assert "OSS_BUCKET" in script
    assert "manifest.json" in script


def test_restore_script_covers_database_and_storage_restore() -> None:
    script = (ROOT_DIR / "scripts" / "restore.sh").read_text(encoding="utf-8")

    assert script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in script
    assert "pg_restore" in script
    assert "BACKUP_DB_MODE" in script
    assert "docker compose" in script
    assert "storage.tar.gz" in script
    assert "BACKUP_DIR" in script


def test_disaster_recovery_doc_records_drill_and_operational_steps() -> None:
    doc = (ROOT_DIR / "docs" / "disaster-recovery.md").read_text(encoding="utf-8")

    for phrase in (
        "T-1-DEPLOY-03",
        "完整一次备份 + 恢复演练通过",
        "scripts/backup.sh",
        "scripts/restore.sh",
        "pg_dump",
        "pg_restore",
        "OSS 占位",
        "演练记录",
        "RPO",
        "RTO",
    ):
        assert phrase in doc
