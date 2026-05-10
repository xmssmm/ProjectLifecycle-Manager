from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Protocol
from uuid import UUID, uuid4

from openpyxl import Workbook  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.departments import Department
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.payments import Payment
from app.models.reports import ReportJob, ReportJobStatus, ReportType
from app.models.sub_projects import SubProject
from app.models.users import User, UserRole
from app.schemas.reports import ReportCreate
from app.storage.base import StorageBackend

REPORT_GENERATOR_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)
ReportTable = tuple[list[str], list[list[object]]]


@dataclass(frozen=True)
class ReportSnapshot:
    departments: Sequence[Department]
    main_projects: Sequence[MainProject]
    sub_projects: Sequence[SubProject]
    payments: Sequence[Payment]


class ReportTaskDispatcher(Protocol):
    def enqueue(self, job_id: UUID) -> None:
        ...


class NoopReportTaskDispatcher:
    def enqueue(self, job_id: UUID) -> None:
        _ = job_id


class ReportRepository(Protocol):
    async def load_snapshot(self) -> ReportSnapshot:
        ...

    async def add_job(self, job: ReportJob) -> ReportJob:
        ...

    async def get_job(self, job_id: UUID) -> ReportJob | None:
        ...

    async def save_job(self, job: ReportJob) -> ReportJob:
        ...


class InMemoryReportRepository:
    def __init__(
        self,
        *,
        departments: Sequence[Department] | None = None,
        main_projects: Sequence[MainProject] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
        payments: Sequence[Payment] | None = None,
    ) -> None:
        self.departments = list(departments or [])
        self.main_projects = list(main_projects or [])
        self.sub_projects = list(sub_projects or [])
        self.payments = list(payments or [])
        self.jobs: dict[UUID, ReportJob] = {}

    async def load_snapshot(self) -> ReportSnapshot:
        return ReportSnapshot(
            departments=self.departments,
            main_projects=self.main_projects,
            sub_projects=self.sub_projects,
            payments=self.payments,
        )

    async def add_job(self, job: ReportJob) -> ReportJob:
        self.jobs[job.id] = job
        return job

    async def get_job(self, job_id: UUID) -> ReportJob | None:
        return self.jobs.get(job_id)

    async def save_job(self, job: ReportJob) -> ReportJob:
        self.jobs[job.id] = job
        return job


class SqlAlchemyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_snapshot(self) -> ReportSnapshot:
        departments = list((await self._session.scalars(select(Department))).all())
        main_projects = list((await self._session.scalars(select(MainProject))).all())
        sub_projects = list((await self._session.scalars(select(SubProject))).all())
        payments = list((await self._session.scalars(select(Payment))).all())
        return ReportSnapshot(
            departments=departments,
            main_projects=main_projects,
            sub_projects=sub_projects,
            payments=payments,
        )

    async def add_job(self, job: ReportJob) -> ReportJob:
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def get_job(self, job_id: UUID) -> ReportJob | None:
        return await self._session.get(ReportJob, job_id)

    async def save_job(self, job: ReportJob) -> ReportJob:
        await self._session.commit()
        await self._session.refresh(job)
        return job


class ReportService:
    def __init__(
        self,
        *,
        repository: ReportRepository,
        storage: StorageBackend,
        dispatcher: ReportTaskDispatcher | None = None,
        async_threshold_rows: int = 1000,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._dispatcher = dispatcher or NoopReportTaskDispatcher()
        self._async_threshold_rows = async_threshold_rows
        self._now_provider = now_provider

    async def create_report(self, *, actor: User, payload: ReportCreate) -> ReportJob:
        self._ensure_can_generate(actor)
        snapshot = await self._repository.load_snapshot()
        headers, rows = self._build_table(
            report_type=payload.report_type,
            snapshot=snapshot,
            parameters=payload.parameters,
        )
        now = self._now_provider()
        job = ReportJob(
            id=uuid4(),
            report_type=payload.report_type,
            requested_by_id=actor.id,
            parameters=dict(payload.parameters),
            status=ReportJobStatus.queued,
            progress=0,
            row_count=len(rows),
            xlsx_storage_key=None,
            pdf_storage_key=None,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._repository.add_job(job)
        if len(rows) >= self._async_threshold_rows:
            self._dispatcher.enqueue(job.id)
            return job
        return await self._generate_and_store(job=job, headers=headers, rows=rows)

    async def get_report_job(self, *, actor: User, job_id: UUID) -> ReportJob:
        job = await self._get_existing_job(job_id)
        if actor.role != UserRole.admin and job.requested_by_id != actor.id:
            raise PermissionDeniedError()
        return job

    async def run_report_job(self, job_id: UUID) -> ReportJob:
        job = await self._get_existing_job(job_id)
        snapshot = await self._repository.load_snapshot()
        headers, rows = self._build_table(
            report_type=job.report_type,
            snapshot=snapshot,
            parameters=job.parameters,
        )
        job.row_count = len(rows)
        return await self._generate_and_store(job=job, headers=headers, rows=rows)

    async def _generate_and_store(
        self,
        *,
        job: ReportJob,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
    ) -> ReportJob:
        now = self._now_provider()
        job.status = ReportJobStatus.running
        job.progress = 10
        job.started_at = now
        job.error_message = None
        job.updated_at = now
        await self._repository.save_job(job)
        try:
            xlsx_content = self._render_xlsx(headers=headers, rows=rows)
            pdf_content = self._render_pdf(job=job, headers=headers, rows=rows)
            job.xlsx_storage_key = self._storage.save(
                sub_id="reports",
                phase_id=str(job.id),
                filename=f"{job.report_type.value}.xlsx",
                content=xlsx_content,
            )
            job.pdf_storage_key = self._storage.save(
                sub_id="reports",
                phase_id=str(job.id),
                filename=f"{job.report_type.value}.pdf",
                content=pdf_content,
            )
            job.status = ReportJobStatus.completed
            job.progress = 100
            job.finished_at = self._now_provider()
            job.updated_at = job.finished_at
            return await self._repository.save_job(job)
        except Exception as exc:
            job.status = ReportJobStatus.failed
            job.progress = 100
            job.error_message = str(exc)
            job.finished_at = self._now_provider()
            job.updated_at = job.finished_at
            await self._repository.save_job(job)
            raise

    async def _get_existing_job(self, job_id: UUID) -> ReportJob:
        job = await self._repository.get_job(job_id)
        if job is None:
            raise ResourceNotFoundError("Report job does not exist")
        return job

    @staticmethod
    def _ensure_can_generate(actor: User) -> None:
        if actor.role not in REPORT_GENERATOR_ROLES:
            raise PermissionDeniedError()

    def _build_table(
        self,
        *,
        report_type: ReportType,
        snapshot: ReportSnapshot,
        parameters: Mapping[str, Any],
    ) -> ReportTable:
        builders = {
            ReportType.project_list: self._build_project_list,
            ReportType.payment_journal: self._build_payment_journal,
            ReportType.dept_summary: self._build_dept_summary,
            ReportType.monthly_summary: self._build_monthly_summary,
        }
        return builders[report_type](snapshot, parameters)

    def _build_project_list(
        self,
        snapshot: ReportSnapshot,
        parameters: Mapping[str, Any],
    ) -> ReportTable:
        sub_projects_by_main = self._sub_projects_by_main(snapshot.sub_projects)
        rows: list[list[object]] = []
        for project in sorted(snapshot.main_projects, key=lambda item: item.project_no):
            if not self._matches_project_filters(project, parameters):
                continue
            sub_projects = sub_projects_by_main.get(project.id, [])
            if not sub_projects:
                rows.append(self._project_row(project, None))
                continue
            for sub_project in sorted(sub_projects, key=lambda item: item.project_no):
                rows.append(self._project_row(project, sub_project))
        return (
            [
                "main_project_no",
                "main_project_name",
                "main_status",
                "dept_id",
                "main_budget",
                "main_spent",
                "sub_project_no",
                "sub_project_name",
                "sub_status",
                "sub_budget",
                "sub_spent",
            ],
            rows,
        )

    def _build_payment_journal(
        self,
        snapshot: ReportSnapshot,
        parameters: Mapping[str, Any],
    ) -> ReportTable:
        sub_projects = {item.id: item for item in snapshot.sub_projects}
        main_projects = {item.id: item for item in snapshot.main_projects}
        rows: list[list[object]] = []
        for payment in sorted(
            snapshot.payments,
            key=lambda item: (item.payment_date, item.payment_no),
        ):
            sub_project = sub_projects.get(payment.sub_project_id)
            if sub_project is None:
                continue
            main_project = main_projects.get(sub_project.main_project_id)
            if main_project is None or not self._matches_project_filters(main_project, parameters):
                continue
            if not self._matches_payment_date(payment.payment_date, parameters):
                continue
            rows.append(
                [
                    payment.payment_no,
                    payment.payment_date,
                    payment.payment_type.value,
                    payment.amount,
                    sub_project.project_no,
                    sub_project.name,
                    main_project.project_no,
                    main_project.name,
                    str(main_project.dept_id),
                ],
            )
        return (
            [
                "payment_no",
                "payment_date",
                "payment_type",
                "amount",
                "sub_project_no",
                "sub_project_name",
                "main_project_no",
                "main_project_name",
                "dept_id",
            ],
            rows,
        )

    def _build_dept_summary(
        self,
        snapshot: ReportSnapshot,
        parameters: Mapping[str, Any],
    ) -> ReportTable:
        departments = {item.id: item for item in snapshot.departments}
        grouped: dict[UUID, list[MainProject]] = {}
        for project in snapshot.main_projects:
            if self._matches_project_filters(project, parameters):
                grouped.setdefault(project.dept_id, []).append(project)
        rows: list[list[object]] = []
        for dept_id, projects in sorted(grouped.items(), key=lambda item: str(item[0])):
            department = departments.get(dept_id)
            rows.append(
                [
                    str(dept_id),
                    department.name if department is not None else "",
                    len(projects),
                    sum((project.total_budget for project in projects), Decimal("0")),
                    sum((project.spent_amount for project in projects), Decimal("0")),
                    self._completion_rate(projects),
                ],
            )
        return (
            [
                "dept_id",
                "dept_name",
                "project_count",
                "total_budget",
                "spent_amount",
                "completed_rate",
            ],
            rows,
        )

    def _build_monthly_summary(
        self,
        snapshot: ReportSnapshot,
        parameters: Mapping[str, Any],
    ) -> ReportTable:
        del parameters
        month_keys = {
            project.created_at.strftime("%Y-%m")
            for project in snapshot.main_projects
        } | {payment.payment_date.strftime("%Y-%m") for payment in snapshot.payments}
        rows: list[list[object]] = []
        for month in sorted(month_keys):
            new_projects = [
                project
                for project in snapshot.main_projects
                if project.created_at.strftime("%Y-%m") == month
            ]
            payments = [
                payment
                for payment in snapshot.payments
                if payment.payment_date.strftime("%Y-%m") == month
            ]
            rows.append(
                [
                    month,
                    len(new_projects),
                    len(payments),
                    sum((payment.amount for payment in payments), Decimal("0")),
                ],
            )
        return (["month", "new_main_projects", "payment_count", "payment_total"], rows)

    @staticmethod
    def _project_row(project: MainProject, sub_project: SubProject | None) -> list[object]:
        return [
            project.project_no,
            project.name,
            project.status.value,
            str(project.dept_id),
            project.total_budget,
            project.spent_amount,
            sub_project.project_no if sub_project else "",
            sub_project.name if sub_project else "",
            sub_project.status.value if sub_project else "",
            sub_project.budget if sub_project else "",
            sub_project.spent_amount if sub_project else "",
        ]

    @staticmethod
    def _sub_projects_by_main(sub_projects: Sequence[SubProject]) -> dict[UUID, list[SubProject]]:
        grouped: dict[UUID, list[SubProject]] = {}
        for sub_project in sub_projects:
            grouped.setdefault(sub_project.main_project_id, []).append(sub_project)
        return grouped

    @staticmethod
    def _matches_project_filters(project: MainProject, parameters: Mapping[str, Any]) -> bool:
        dept_id = parameters.get("dept_id")
        main_project_id = parameters.get("main_project_id")
        return (
            (dept_id is None or str(project.dept_id) == str(dept_id))
            and (main_project_id is None or str(project.id) == str(main_project_id))
        )

    @staticmethod
    def _matches_payment_date(payment_date: date, parameters: Mapping[str, Any]) -> bool:
        date_from = ReportService._parse_date(parameters.get("date_from"))
        date_to = ReportService._parse_date(parameters.get("date_to"))
        return (date_from is None or payment_date >= date_from) and (
            date_to is None or payment_date <= date_to
        )

    @staticmethod
    def _parse_date(value: object) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _completion_rate(projects: Sequence[MainProject]) -> str:
        if not projects:
            return "0.00%"
        completed = sum(
            1
            for project in projects
            if project.status in {MainProjectStatus.completed, MainProjectStatus.closed}
        )
        return f"{completed / len(projects) * 100:.2f}%"

    @staticmethod
    def _render_xlsx(*, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> bytes:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "report"
        worksheet.append(list(headers))
        for row in rows:
            worksheet.append([ReportService._cell_value(value) for value in row])
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _render_pdf(
        *,
        job: ReportJob,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
    ) -> bytes:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 42
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(42, y, f"Report: {job.report_type.value}")
        y -= 24
        pdf.setFont("Helvetica", 8)
        pdf.drawString(42, y, " | ".join(headers[:6]))
        y -= 16
        for row in rows[:120]:
            if y < 42:
                pdf.showPage()
                pdf.setFont("Helvetica", 8)
                y = height - 42
            row_text = " | ".join(str(ReportService._cell_value(value)) for value in row[:6])
            pdf.drawString(42, y, row_text)
            y -= 14
        if len(rows) > 120:
            pdf.drawString(42, y, f"... {len(rows) - 120} more rows")
        pdf.save()
        _ = width
        return buffer.getvalue()

    @staticmethod
    def _cell_value(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value.quantize(Decimal("0.01")))
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value
