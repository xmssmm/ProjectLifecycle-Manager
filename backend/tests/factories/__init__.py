# mypy: ignore-errors
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import factory

from app.models.departments import Department
from app.models.documents import Document
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.payments import Payment, PaymentType
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole, UserStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


class DepartmentFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = Department

    id = factory.LazyFunction(uuid4)
    code = factory.Sequence(lambda value: f"DEPT-{value:03d}")
    name = factory.Sequence(lambda value: f"部门 {value}")
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class UserFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = User

    id = factory.LazyFunction(uuid4)
    username = factory.Sequence(lambda value: f"user-{value}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.local")
    password_hash = "hashed"
    role = UserRole.proj_member
    dept_id = None
    status = UserStatus.active
    password_changed_at = factory.LazyFunction(utc_now)
    last_login_at = None
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class MainProjectFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = MainProject

    id = factory.LazyFunction(uuid4)
    project_no = factory.Sequence(lambda value: f"Z-2026-{value:04d}")
    name = factory.Sequence(lambda value: f"主项目 {value}")
    dept_id = factory.LazyFunction(uuid4)
    status = MainProjectStatus.in_progress
    total_budget = Decimal("100000.00")
    expected_finish_date = date(2026, 12, 31)
    spent_amount = Decimal("0.00")
    remark = None
    creator_id = factory.LazyFunction(uuid4)
    reviews = []
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class SubProjectFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = SubProject

    id = factory.LazyFunction(uuid4)
    project_no = factory.Sequence(lambda value: f"Z-2026-0001-ZX-{value:03d}")
    name = factory.Sequence(lambda value: f"子项目 {value}")
    main_project_id = factory.LazyFunction(uuid4)
    dept_id = factory.LazyFunction(uuid4)
    budget = Decimal("50000.00")
    manager_id = factory.LazyFunction(uuid4)
    creator_id = factory.LazyFunction(uuid4)
    status = SubProjectStatus.in_progress
    plan_end_date = date(2026, 12, 31)
    actual_end_date = None
    spent_amount = Decimal("0.00")
    remark = None
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class PhaseFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = Phase

    id = factory.LazyFunction(uuid4)
    sub_project_id = factory.LazyFunction(uuid4)
    phase_no = 1
    code = "initiation"
    name = "立项"
    status = PhaseStatus.in_progress
    enter_at = factory.LazyFunction(utc_now)
    finish_at = None
    procurement_type = None
    histories = []
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class TaskFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = Task

    id = factory.LazyFunction(uuid4)
    task_no = factory.Sequence(lambda value: f"Z-2026-0001-ZX-001-T-{value:03d}")
    sub_project_id = factory.LazyFunction(uuid4)
    phase_id = factory.LazyFunction(uuid4)
    name = factory.Sequence(lambda value: f"任务 {value}")
    plan_end_date = date(2026, 5, 31)
    status = TaskStatus.in_progress
    executors = []
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class TaskExecutorFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = TaskExecutor

    id = factory.LazyFunction(uuid4)
    task_id = factory.LazyFunction(uuid4)
    user_id = factory.LazyFunction(uuid4)
    plan_end_date = date(2026, 5, 31)
    actual_end_date = None
    status = TaskStatus.in_progress
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class DocumentFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = Document

    id = factory.LazyFunction(uuid4)
    doc_no = factory.LazyFunction(lambda: str(uuid4()))
    sub_project_id = factory.LazyFunction(uuid4)
    phase_id = factory.LazyFunction(uuid4)
    acceptance_step_id = None
    doc_type = "meeting_material"
    file_name = "meeting.pdf"
    file_path = factory.LazyAttribute(
        lambda obj: f"{obj.sub_project_id}/{obj.phase_id}/meeting.pdf",
    )
    file_size = 128
    version = 1
    is_latest = True
    is_deleted = False
    uploader_id = factory.LazyFunction(uuid4)
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)


class PaymentFactory(factory.Factory):  # type: ignore[misc]
    class Meta:
        model = Payment

    id = factory.LazyFunction(uuid4)
    payment_no = factory.Sequence(lambda value: f"PAY-2026-{value:04d}")
    sub_project_id = factory.LazyFunction(uuid4)
    amount = Decimal("1000.00")
    payment_date = date(2026, 5, 10)
    remark = None
    payment_type = PaymentType.normal
    reverses_payment_id = None
    operator_id = factory.LazyFunction(uuid4)
    vouchers = []
    created_at = factory.LazyFunction(utc_now)
    updated_at = factory.LazyFunction(utc_now)
