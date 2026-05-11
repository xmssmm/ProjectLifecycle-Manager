from __future__ import annotations

CELERY_SMOKE_TASK_NAME = "app.tasks.celery_app.ping"
TASK_DEADLINE_SCAN_TASK_NAME = "app.tasks.task_deadlines.scan_task_deadlines"
DOCUMENT_SCAN_TASK_NAME = "app.tasks.document_scanning.scan_document_file"
DOCUMENT_SEARCH_INDEX_TASK_NAME = "app.tasks.search.index_document_search"
DATABASE_EXPORT_TASK_NAME = "app.tasks.database_exports.generate_database_export"
FILE_CLEANUP_TASK_NAME = "app.tasks.file_cleanup.cleanup_storage_files"
AUDIT_PARTITION_TASK_NAME = "app.tasks.audit_partitions.ensure_audit_partitions"
REPORT_GENERATE_TASK_NAME = "app.tasks.reports.generate_report"
REPORT_CLEANUP_TASK_NAME = "app.tasks.reports.cleanup_expired_reports"
NOTIFICATION_DIGEST_TASK_NAME = "app.tasks.notifications.generate_notification_digest"
NOTIFICATION_DELIVERY_RETRY_TASK_NAME = (
    "app.tasks.notification_delivery.retry_notification_deliveries"
)
WEBHOOK_DELIVERY_RETRY_TASK_NAME = "app.tasks.webhooks.retry_webhook_deliveries"
