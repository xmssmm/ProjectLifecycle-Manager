from __future__ import annotations

from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_docker_compose_defines_celery_worker_and_beat_services() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8"))

    worker = compose["services"]["celery-worker"]
    beat = compose["services"]["celery-beat"]

    assert worker["build"]["context"] == "./backend"
    assert worker["command"] == [
        "celery",
        "-A",
        "app.tasks.celery_app:celery_app",
        "worker",
        "--loglevel=info",
    ]
    assert worker["environment"]["REDIS_URL"] == "${REDIS_URL:-redis://redis:6379/0}"
    assert worker["depends_on"]["redis"]["condition"] == "service_healthy"

    assert beat["build"]["context"] == "./backend"
    assert beat["command"] == [
        "celery",
        "-A",
        "app.tasks.celery_app:celery_app",
        "beat",
        "--loglevel=info",
    ]
    assert beat["environment"]["REDIS_URL"] == "${REDIS_URL:-redis://redis:6379/0}"
    assert beat["depends_on"]["redis"]["condition"] == "service_healthy"
