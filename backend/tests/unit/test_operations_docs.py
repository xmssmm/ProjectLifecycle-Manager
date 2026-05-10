from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_release_checklist_guides_a_new_operator_through_go_live() -> None:
    doc = (ROOT_DIR / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    for phrase in (
        "T-1-DEPLOY-04",
        "数据库迁移",
        "seed",
        "备份",
        "监控",
        "告警",
        "回滚预案",
        "docker compose -f docker-compose.prod.yml",
        "alembic upgrade head",
        "scripts/backup.sh",
        "/health",
        "/metrics",
    ):
        assert phrase in doc


def test_operations_manual_covers_daily_operator_tasks() -> None:
    doc = (ROOT_DIR / "docs" / "operations.md").read_text(encoding="utf-8")

    for phrase in (
        "添加 admin",
        "查日志",
        "清缓存",
        "Celery 重启",
        "docker compose -f docker-compose.prod.yml logs",
        "docker compose -f docker-compose.prod.yml restart celery-worker",
        "redis-cli",
        "scripts/backup.sh",
        "Grafana",
    ):
        assert phrase in doc


def test_troubleshooting_manual_covers_common_failures() -> None:
    doc = (ROOT_DIR / "docs" / "troubleshooting.md").read_text(encoding="utf-8")

    for phrase in (
        "常见问题",
        "登录失败",
        "数据库连接失败",
        "Redis 连接失败",
        "文件上传失败",
        "Celery 任务不执行",
        "迁移失败",
        "Grafana 无数据",
        "docker compose -f docker-compose.prod.yml ps",
        "回滚",
    ):
        assert phrase in doc
