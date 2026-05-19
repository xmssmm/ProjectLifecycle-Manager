"""SQLAlchemy models package."""

from app.models.acceptance_steps import AcceptanceStep, AcceptanceStepStatus
from app.models.ai import AiAuditLog, AiAuditStatus
from app.models.api_keys import ApiKey
from app.models.archives import ArchiveBatch, ArchiveMainProject, ArchiveSubProject
from app.models.audit_logs import AuditLog
from app.models.base import Base
from app.models.custom_reports import (
    CustomReportDefinition,
    CustomReportRun,
    CustomReportRunStatus,
    CustomReportScheduleFrequency,
    CustomReportShareScope,
)
from app.models.departments import Department
from app.models.documents import Document, DocumentScanStatus
from app.models.exports import DatabaseExportJob, DatabaseExportJobStatus
from app.models.handover_requests import (
    HandoverRequest,
    HandoverRequestProject,
    HandoverRequestStatus,
)
from app.models.main_projects import (
    MainProject,
    MainProjectStatus,
    ProjectReview,
    ProjectReviewDecision,
)
from app.models.notification_deliveries import NotificationDelivery, NotificationDeliveryStatus
from app.models.notifications import Notification, NotificationPreference
from app.models.oauth import OAuthBinding
from app.models.payments import Payment, PaymentType, PaymentVoucher
from app.models.phases import (
    Phase,
    PhaseDocRequirement,
    PhaseDocTemplate,
    PhaseHistory,
    PhaseStatus,
    ProcurementType,
)
from app.models.project_taxonomy import (
    ProjectCategory,
    ProjectTag,
    ProjectTemplate,
    ProjectTemplateScope,
)
from app.models.project_types import ProjectType
from app.models.reports import ReportJob, ReportJobStatus, ReportType
from app.models.revoke_requests import (
    RevokeRequest,
    RevokeRequestStatus,
    RevokeReviewDecision,
)
from app.models.role_permissions import RolePermission
from app.models.search import DocumentSearchEntry, DocumentSearchStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectHandover,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectNoCounter,
    SubProjectStatus,
)
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole, UserStatus
from app.models.webhooks import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint
from app.models.workflows import (
    WorkflowTemplate,
    WorkflowTemplateStatus,
    WorkflowTemplateVersion,
)

__all__ = [
    "Base",
    "AcceptanceStep",
    "AcceptanceStepStatus",
    "AiAuditLog",
    "AiAuditStatus",
    "ApiKey",
    "ArchiveBatch",
    "ArchiveMainProject",
    "ArchiveSubProject",
    "AuditLog",
    "CustomReportDefinition",
    "CustomReportRun",
    "CustomReportRunStatus",
    "CustomReportScheduleFrequency",
    "CustomReportShareScope",
    "Department",
    "Document",
    "DocumentScanStatus",
    "DatabaseExportJob",
    "DatabaseExportJobStatus",
    "DocumentSearchEntry",
    "DocumentSearchStatus",
    "HandoverRequest",
    "HandoverRequestProject",
    "HandoverRequestStatus",
    "MainProject",
    "MainProjectStatus",
    "ProjectReview",
    "ProjectReviewDecision",
    "ProjectType",
    "ProjectCategory",
    "ProjectTag",
    "ProjectTemplate",
    "ProjectTemplateScope",
    "SubProject",
    "SubProjectHandover",
    "SubProjectMember",
    "SubProjectMemberRole",
    "SubProjectNoCounter",
    "SubProjectStatus",
    "Task",
    "TaskExecutor",
    "TaskStatus",
    "Payment",
    "PaymentType",
    "PaymentVoucher",
    "RevokeRequest",
    "RevokeRequestStatus",
    "RevokeReviewDecision",
    "ReportJob",
    "ReportJobStatus",
    "ReportType",
    "RolePermission",
    "Notification",
    "NotificationDelivery",
    "NotificationDeliveryStatus",
    "NotificationPreference",
    "OAuthBinding",
    "Phase",
    "PhaseDocRequirement",
    "PhaseDocTemplate",
    "PhaseHistory",
    "PhaseStatus",
    "ProcurementType",
    "User",
    "UserRole",
    "UserStatus",
    "WebhookDelivery",
    "WebhookDeliveryStatus",
    "WebhookEndpoint",
    "WorkflowTemplate",
    "WorkflowTemplateStatus",
    "WorkflowTemplateVersion",
]
