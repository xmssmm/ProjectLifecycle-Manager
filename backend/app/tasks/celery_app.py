from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import Settings, get_settings

CELERY_SMOKE_TASK_NAME = "app.tasks.celery_app.ping"


def create_celery_app(settings: Settings | None = None) -> Celery:
    resolved_settings = settings or get_settings()
    app = Celery(
        "project_management",
        broker=resolved_settings.effective_celery_broker_url,
        backend=resolved_settings.effective_celery_result_backend,
    )
    app.conf.update(
        accept_content=["json"],
        beat_schedule={
            "celery-smoke-ping-every-minute": {
                "task": CELERY_SMOKE_TASK_NAME,
                "schedule": 60.0,
            },
        },
        result_serializer="json",
        task_serializer="json",
        timezone="Asia/Shanghai",
    )

    @app.task(name=CELERY_SMOKE_TASK_NAME)  # type: ignore[untyped-decorator]
    def ping() -> str:
        return "pong"

    return app


celery_app = create_celery_app()
