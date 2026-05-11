from __future__ import annotations

from pathlib import Path

from app.models.documents import Document
from app.models.main_projects import MainProject
from app.models.payments import Payment
from app.models.reports import ReportJob
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.tasks import Task, TaskExecutor

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    REPO_ROOT / "backend" / "alembic" / "versions" / "0032_add_query_performance_indexes.py"
)
BASELINE_PATH = REPO_ROOT / "docs" / "PERFORMANCE_BASELINE.md"


def table_index_names(model: type[object]) -> set[str]:
    return {index.name or "" for index in model.__table__.indexes}  # type: ignore[attr-defined]


def test_phase4_query_indexes_are_declared_on_models() -> None:
    expected = {
        MainProject: {
            "ix_main_projects_created_at",
            "ix_main_projects_status_created_at",
            "ix_main_projects_dept_created_at",
        },
        SubProject: {
            "ix_sub_projects_created_at",
            "ix_sub_projects_manager_created_at",
            "ix_sub_projects_status_created_at",
            "ix_sub_projects_dept_created_at",
        },
        SubProjectMember: {"ix_sub_project_members_user_sub_project"},
        Document: {
            "ix_documents_sub_project_latest_created",
            "ix_documents_phase_latest_doc_type",
        },
        Task: {"ix_tasks_status_plan_end_date"},
        TaskExecutor: {"ix_task_executors_user_status"},
        Payment: {"ix_payments_payment_date"},
        ReportJob: {"ix_report_jobs_status_finished_at"},
    }

    for model, index_names in expected.items():
        assert index_names.issubset(table_index_names(model))


def test_phase4_query_index_migration_covers_critical_query_paths() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    for index_name in (
        "ix_main_projects_created_at",
        "ix_main_projects_status_created_at",
        "ix_main_projects_dept_created_at",
        "ix_sub_projects_created_at",
        "ix_sub_projects_manager_created_at",
        "ix_sub_projects_status_created_at",
        "ix_sub_projects_dept_created_at",
        "ix_sub_project_members_user_sub_project",
        "ix_documents_sub_project_latest_created",
        "ix_documents_phase_latest_doc_type",
        "ix_tasks_status_plan_end_date",
        "ix_task_executors_user_status",
        "ix_payments_payment_date",
        "ix_report_jobs_status_finished_at",
    ):
        assert index_name in source


def test_phase4_performance_baseline_document_records_before_after_metrics() -> None:
    report = BASELINE_PATH.read_text(encoding="utf-8")

    assert "T-4-PERF-04" in report
    assert "P99 <= 800ms" in report
    assert "优化前" in report
    assert "优化后" in report
    assert "复测命令" in report
    for query_name in (
        "main_project_list",
        "sub_project_list",
        "dashboard",
        "reports",
        "document_list",
    ):
        assert query_name in report
