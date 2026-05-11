from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from app.core.config import Settings, get_settings
from app.tasks.task_names import (
    AUDIT_PARTITION_TASK_NAME,
    CELERY_SMOKE_TASK_NAME,
    FILE_CLEANUP_TASK_NAME,
    NOTIFICATION_DELIVERY_RETRY_TASK_NAME,
    NOTIFICATION_DIGEST_TASK_NAME,
    REPORT_CLEANUP_TASK_NAME,
    TASK_DEADLINE_SCAN_TASK_NAME,
    WEBHOOK_DELIVERY_RETRY_TASK_NAME,
)


def create_celery_app(settings: Settings | None = None) -> Celery:
    resolved_settings = settings or get_settings()
    app = Celery(
        "project_management",
        broker=resolved_settings.effective_celery_broker_url,
        backend=resolved_settings.effective_celery_result_backend,
        include=[
            "app.tasks.task_deadlines",
            "app.tasks.file_cleanup",
            "app.tasks.audit_partitions",
            "app.tasks.reports",
            "app.tasks.notifications",
            "app.tasks.notification_delivery",
            "app.tasks.webhooks",
            "app.tasks.document_scanning",
        ],
    )
    app.conf.update(
        accept_content=["json"],
        beat_schedule={
            "celery-smoke-ping-every-minute": {
                "task": CELERY_SMOKE_TASK_NAME,
                "schedule": 60.0,
            },
            "task-deadline-scan-hourly-by-timezone": {
                "task": TASK_DEADLINE_SCAN_TASK_NAME,
                "schedule": crontab(minute=0),
            },
            "notification-digest-hourly-by-timezone": {
                "task": NOTIFICATION_DIGEST_TASK_NAME,
                "schedule": crontab(minute=0),
            },
            "notification-delivery-retry-every-minute": {
                "task": NOTIFICATION_DELIVERY_RETRY_TASK_NAME,
                "schedule": 60.0,
            },
            "webhook-delivery-retry-every-minute": {
                "task": WEBHOOK_DELIVERY_RETRY_TASK_NAME,
                "schedule": 60.0,
            },
            "file-cleanup-weekly-monday-0300": {
                "task": FILE_CLEANUP_TASK_NAME,
                "schedule": crontab(minute=0, hour=3, day_of_week="monday"),
            },
            "audit-partition-maintenance-monthly-0030": {
                "task": AUDIT_PARTITION_TASK_NAME,
                "schedule": crontab(minute=30, hour=0, day_of_month=1),
            },
            "report-cleanup-daily-0330": {
                "task": REPORT_CLEANUP_TASK_NAME,
                "schedule": crontab(minute=30, hour=3),
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
