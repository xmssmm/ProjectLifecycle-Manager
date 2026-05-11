from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.users import User, UserRole, UserStatus
from app.schemas.custom_reports import (
    ReportFilterConfig,
    ReportMetricConfig,
    ReportQueryConfig,
    ReportSortConfig,
    SortDirection,
)
from app.services.report_datasets import (
    DatasetAggregate,
    DatasetFilterOperator,
    default_report_dataset_registry,
)
from app.services.report_query_compiler import ReportQueryCompiler


def make_user(role: UserRole, *, username: str = "user") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_compiler() -> ReportQueryCompiler:
    return ReportQueryCompiler(registry=default_report_dataset_registry())


def test_report_query_compiler_rejects_unknown_dataset() -> None:
    compiler = make_compiler()
    actor = make_user(UserRole.admin, username="admin")
    config = ReportQueryConfig(
        dataset="main_projects;drop table users",
        dimensions=["project_no"],
    )

    with pytest.raises(ValidationFailedError) as exc:
        compiler.compile(actor=actor, config=config)

    assert "未注册" in exc.value.message


@pytest.mark.parametrize(
    "config",
    [
        ReportQueryConfig(dataset="project_overview", dimensions=["unknown_field"]),
        ReportQueryConfig(
            dataset="project_overview",
            metrics=[
                ReportMetricConfig(
                    field="project_no",
                    aggregate=DatasetAggregate.sum,
                    alias="bad_sum",
                ),
            ],
        ),
        ReportQueryConfig(
            dataset="project_overview",
            filters=[
                ReportFilterConfig(
                    field="total_budget",
                    op=DatasetFilterOperator.contains,
                    value="100",
                ),
            ],
        ),
    ],
)
def test_report_query_compiler_rejects_unregistered_or_unsupported_config(
    config: ReportQueryConfig,
) -> None:
    compiler = make_compiler()
    actor = make_user(UserRole.admin, username="admin")

    with pytest.raises(ValidationFailedError):
        compiler.compile(actor=actor, config=config)


def test_report_query_compiler_injects_project_leader_scope() -> None:
    compiler = make_compiler()
    actor = make_user(UserRole.proj_leader, username="leader")
    config = ReportQueryConfig(
        dataset="project_overview",
        dimensions=["project_no"],
        metrics=[
            ReportMetricConfig(
                field="id",
                aggregate=DatasetAggregate.count,
                alias="project_count",
            ),
        ],
    )

    compiled = compiler.compile(actor=actor, config=config)

    assert compiled.scope.mode == "owned_sub_projects"
    assert compiled.bound_parameters["actor_id"] == actor.id
    statement_text = str(compiled.statement)
    assert "sub_projects" in statement_text
    assert "manager_id" in statement_text


def test_report_query_compiler_builds_statement_and_result_metadata() -> None:
    compiler = make_compiler()
    actor = make_user(UserRole.admin, username="admin")
    config = ReportQueryConfig(
        dataset="payment_execution",
        dimensions=["dept_id"],
        metrics=[
            ReportMetricConfig(
                field="amount",
                aggregate=DatasetAggregate.sum,
                alias="total_amount",
            ),
        ],
        filters=[
            ReportFilterConfig(
                field="payment_date",
                op=DatasetFilterOperator.gte,
                value=date(2026, 1, 1),
            ),
        ],
        sort=[
            ReportSortConfig(
                field="total_amount",
                direction=SortDirection.desc,
            ),
        ],
        limit=50,
    )

    compiled = compiler.compile(actor=actor, config=config)

    assert [column.key for column in compiled.columns] == ["dept_id", "total_amount"]
    assert compiled.columns[1].aggregate == DatasetAggregate.sum
    assert compiled.limit == 50
    assert compiled.bound_parameters["filter_0"] == date(2026, 1, 1)
    assert "payments" in str(compiled.statement)
