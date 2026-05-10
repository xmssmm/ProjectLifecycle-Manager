from __future__ import annotations

from importlib import import_module
from types import ModuleType

import pytest

from app.core.config import Settings


def load_celery_module() -> ModuleType:
    try:
        return import_module("app.tasks.celery_app")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.tasks.celery_app is required: {exc}")


def test_celery_app_uses_redis_json_and_fixed_timezone() -> None:
    celery_module = load_celery_module()
    settings = Settings(redis_url="redis://redis:6379/0")

    celery_app = celery_module.create_celery_app(settings)

    assert celery_app.conf.broker_url == "redis://redis:6379/0"
    assert celery_app.conf.result_backend == "redis://redis:6379/0"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "Asia/Shanghai"


def test_celery_app_registers_smoke_task_for_beat() -> None:
    celery_module = load_celery_module()
    celery_app = celery_module.create_celery_app(Settings(redis_url="redis://redis:6379/0"))

    assert celery_module.CELERY_SMOKE_TASK_NAME in celery_app.tasks
    assert celery_app.conf.beat_schedule["celery-smoke-ping-every-minute"] == {
        "task": celery_module.CELERY_SMOKE_TASK_NAME,
        "schedule": 60.0,
    }


def test_celery_app_schedules_notification_digest_daily_0900() -> None:
    celery_module = load_celery_module()
    celery_app = celery_module.create_celery_app(Settings(redis_url="redis://redis:6379/0"))

    from app.tasks.task_names import NOTIFICATION_DIGEST_TASK_NAME

    schedule = celery_app.conf.beat_schedule["notification-digest-daily-0900"]
    assert celery_app.conf.timezone == "Asia/Shanghai"
    assert schedule["task"] == NOTIFICATION_DIGEST_TASK_NAME
    assert "0 9 * * *" in str(schedule["schedule"])
