from __future__ import annotations

CELERY_SMOKE_TASK_NAME = "app.tasks.celery_app.ping"
TASK_DEADLINE_SCAN_TASK_NAME = "app.tasks.task_deadlines.scan_task_deadlines"
FILE_CLEANUP_TASK_NAME = "app.tasks.file_cleanup.cleanup_storage_files"
AUDIT_PARTITION_TASK_NAME = "app.tasks.audit_partitions.ensure_audit_partitions"
REPORT_GENERATE_TASK_NAME = "app.tasks.reports.generate_report"
