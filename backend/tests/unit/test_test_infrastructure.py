from __future__ import annotations

from decimal import Decimal
from typing import cast

from app.models.departments import Department
from app.models.documents import Document
from app.models.main_projects import MainProject
from app.models.payments import Payment
from app.models.phases import Phase
from app.models.sub_projects import SubProject
from app.models.tasks import Task, TaskExecutor
from app.models.users import User, UserRole
from tests.conftest import normalize_asyncpg_url
from tests.factories import (
    DepartmentFactory,
    DocumentFactory,
    MainProjectFactory,
    PaymentFactory,
    PhaseFactory,
    SubProjectFactory,
    TaskExecutorFactory,
    TaskFactory,
    UserFactory,
)


def test_core_factories_build_valid_model_instances() -> None:
    admin = cast(User, UserFactory(role=UserRole.admin))
    department = cast(Department, DepartmentFactory())
    main_project = cast(MainProject, MainProjectFactory(dept_id=department.id, creator_id=admin.id))
    sub_project = cast(
        SubProject,
        SubProjectFactory(main_project_id=main_project.id, dept_id=department.id),
    )
    phase = cast(Phase, PhaseFactory(sub_project_id=sub_project.id))
    task = cast(Task, TaskFactory(sub_project_id=sub_project.id, phase_id=phase.id))
    executor = cast(TaskExecutor, TaskExecutorFactory(task_id=task.id, user_id=admin.id))
    document = cast(
        Document,
        DocumentFactory(
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            uploader_id=admin.id,
        ),
    )
    payment = cast(Payment, PaymentFactory(sub_project_id=sub_project.id, operator_id=admin.id))

    assert isinstance(admin, User)
    assert isinstance(main_project, MainProject)
    assert main_project.total_budget == Decimal("100000.00")
    assert task.executors == []
    assert isinstance(executor, TaskExecutor)
    assert document.file_path.endswith(".pdf")
    assert isinstance(payment, Payment)


def test_postgres_testcontainer_url_is_normalized_for_asyncpg() -> None:
    assert (
        normalize_asyncpg_url("postgresql+psycopg2://user:pass@localhost:5432/test")
        == "postgresql+asyncpg://user:pass@localhost:5432/test"
    )
    assert (
        normalize_asyncpg_url("postgresql://user:pass@localhost:5432/test")
        == "postgresql+asyncpg://user:pass@localhost:5432/test"
    )
