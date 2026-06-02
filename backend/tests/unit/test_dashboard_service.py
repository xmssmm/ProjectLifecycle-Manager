from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import PermissionDeniedError
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.payments import Payment, PaymentType
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole, UserStatus
from app.services.dashboard import (
    CACHE_TTL_SECONDS,
    DashboardService,
    DashboardSnapshot,
    InMemoryDashboardCache,
    InMemoryDashboardRepository,
)


def make_user(role: UserRole, *, username: str, dept_id: UUID | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=dept_id,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_main_project(*, dept_id: UUID, status: MainProjectStatus) -> MainProject:
    now = datetime(2026, 5, 10, tzinfo=UTC)
    return MainProject(
        id=uuid4(),
        project_no=f"Z-2026-{uuid4().hex[:4]}",
        name="main",
        dept_id=dept_id,
        status=status,
        total_budget=Decimal("1000.00"),
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark=None,
        creator_id=None,
        created_at=now,
        updated_at=now,
    )


def make_sub_project(
    *,
    main_project: MainProject,
    manager_id: UUID,
    status: SubProjectStatus,
    spent_amount: Decimal = Decimal("0.00"),
) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no=f"{main_project.project_no}-001",
        name="sub",
        main_project_id=main_project.id,
        dept_id=main_project.dept_id,
        budget=Decimal("500.00"),
        manager_id=manager_id,
        creator_id=None,
        status=status,
        plan_end_date=date(2026, 6, 30),
        actual_end_date=None,
        spent_amount=spent_amount,
        remark=None,
        created_at=now,
        updated_at=now,
    )


def make_task(
    *,
    sub_project_id: UUID,
    user_id: UUID,
    plan_end_date: date,
) -> tuple[Task, TaskExecutor]:
    now = datetime.now(UTC)
    task = Task(
        id=uuid4(),
        task_no=f"T-{uuid4().hex[:6]}",
        sub_project_id=sub_project_id,
        phase_id=uuid4(),
        name="task",
        plan_end_date=plan_end_date,
        status=TaskStatus.in_progress,
        created_at=now,
        updated_at=now,
    )
    executor = TaskExecutor(
        id=uuid4(),
        task_id=task.id,
        user_id=user_id,
        plan_end_date=plan_end_date,
        actual_end_date=None,
        status=TaskStatus.in_progress,
        created_at=now,
        updated_at=now,
    )
    return task, executor


def make_payment(*, sub_project_id: UUID, amount: Decimal, payment_date: date) -> Payment:
    now = datetime.now(UTC)
    return Payment(
        id=uuid4(),
        payment_no=f"P-{uuid4().hex[:6]}",
        sub_project_id=sub_project_id,
        amount=amount,
        payment_date=payment_date,
        remark=None,
        payment_type=PaymentType.normal if amount >= 0 else PaymentType.reversal,
        reverses_payment_id=None,
        operator_id=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_admin_dept_and_finance_dashboards_cover_role_specific_metrics() -> None:
    dept_id = uuid4()
    admin = make_user(UserRole.admin, username="admin")
    dept_manager = make_user(UserRole.dept_manager, username="dept-manager", dept_id=dept_id)
    finance = make_user(UserRole.finance_manager, username="finance")
    active_main = make_main_project(dept_id=dept_id, status=MainProjectStatus.in_progress)
    completed_main = make_main_project(dept_id=dept_id, status=MainProjectStatus.completed)
    over_budget_sub = make_sub_project(
        main_project=active_main,
        manager_id=uuid4(),
        status=SubProjectStatus.in_progress,
        spent_amount=Decimal("650.00"),
    )
    unpaid_sub = make_sub_project(
        main_project=completed_main,
        manager_id=uuid4(),
        status=SubProjectStatus.not_started,
    )
    payment = make_payment(
        sub_project_id=over_budget_sub.id,
        amount=Decimal("650.00"),
        payment_date=date(2026, 5, 9),
    )
    due_task, due_executor = make_task(
        sub_project_id=over_budget_sub.id,
        user_id=admin.id,
        plan_end_date=date(2026, 5, 11),
    )
    snapshot = DashboardSnapshot(
        users=[admin, dept_manager, finance],
        main_projects=[active_main, completed_main],
        sub_projects=[over_budget_sub, unpaid_sub],
        sub_project_members=[],
        tasks=[due_task],
        task_executors=[due_executor],
        phases=[],
        payments=[payment],
    )
    service = DashboardService(
        repository=InMemoryDashboardRepository(snapshot),
        cache=InMemoryDashboardCache(),
        today_provider=lambda: date(2026, 5, 10),
    )

    admin_dashboard = await service.get_dashboard(actor=admin, role_scope=UserRole.admin)
    dept_dashboard = await service.get_dashboard(
        actor=dept_manager,
        role_scope=UserRole.dept_manager,
    )
    finance_dashboard = await service.get_dashboard(
        actor=finance,
        role_scope=UserRole.finance_manager,
    )

    assert admin_dashboard["metrics"]["total_users"] == 3
    assert admin_dashboard["metrics"]["over_budget_sub_projects"] == 1
    assert admin_dashboard["metrics"]["due_soon_tasks"] == 1
    assert dept_dashboard["metrics"]["current_month_new_projects"] == 2
    assert dept_dashboard["charts"]["department_project_counts"] == [
        {"label": str(dept_id), "value": 2},
    ]
    assert finance_dashboard["metrics"]["current_month_payment_total"] == "650.00"
    assert finance_dashboard["metrics"]["total_budget"] == "2000.00"
    assert finance_dashboard["lists"]["unpaid_sub_projects"] == [
        {"id": str(unpaid_sub.id), "name": "sub", "status": "not_started"},
    ]


@pytest.mark.asyncio
async def test_dashboard_rejects_non_admin_cross_role_access() -> None:
    member = make_user(UserRole.proj_member, username="member")
    service = DashboardService(
        repository=InMemoryDashboardRepository(
            DashboardSnapshot(
                users=[member],
                main_projects=[],
                sub_projects=[],
                sub_project_members=[],
                tasks=[],
                task_executors=[],
                phases=[],
                payments=[],
            ),
        ),
        cache=InMemoryDashboardCache(),
    )

    with pytest.raises(PermissionDeniedError):
        await service.get_dashboard(actor=member, role_scope=UserRole.finance_manager)


@pytest.mark.asyncio
async def test_project_leader_dashboard_is_limited_to_managed_sub_projects() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    other_leader = make_user(UserRole.proj_leader, username="other")
    main_project = make_main_project(dept_id=uuid4(), status=MainProjectStatus.in_progress)
    own_sub = make_sub_project(
        main_project=main_project,
        manager_id=leader.id,
        status=SubProjectStatus.in_progress,
    )
    other_sub = make_sub_project(
        main_project=main_project,
        manager_id=other_leader.id,
        status=SubProjectStatus.completed,
        spent_amount=Decimal("900.00"),
    )
    own_phase = Phase(
        id=uuid4(),
        sub_project_id=own_sub.id,
        phase_no=2,
        code="procurement",
        name="procurement",
        status=PhaseStatus.in_progress,
        enter_at=datetime.now(UTC),
        finish_at=None,
        procurement_type=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    own_task, own_executor = make_task(
        sub_project_id=own_sub.id,
        user_id=leader.id,
        plan_end_date=date(2026, 5, 12),
    )
    other_task, other_executor = make_task(
        sub_project_id=other_sub.id,
        user_id=other_leader.id,
        plan_end_date=date(2026, 5, 12),
    )
    service = DashboardService(
        repository=InMemoryDashboardRepository(
            DashboardSnapshot(
                users=[leader, other_leader],
                main_projects=[main_project],
                sub_projects=[own_sub, other_sub],
                sub_project_members=[],
                tasks=[own_task, other_task],
                task_executors=[own_executor, other_executor],
                phases=[own_phase],
                payments=[],
            ),
        ),
        cache=InMemoryDashboardCache(),
        today_provider=lambda: date(2026, 5, 10),
    )

    dashboard = await service.get_dashboard(actor=leader, role_scope=UserRole.proj_leader)

    assert dashboard["role_scope"] == "proj_leader"
    assert dashboard["cache_ttl_seconds"] == CACHE_TTL_SECONDS
    assert dashboard["metrics"]["managed_sub_projects"] == 1
    assert dashboard["metrics"]["due_or_overdue_tasks"] == 1
    assert dashboard["charts"]["sub_project_status"] == [{"label": "in_progress", "value": 1}]
    assert dashboard["lists"]["phases_to_promote"][0]["sub_project_id"] == str(own_sub.id)


@pytest.mark.asyncio
async def test_project_member_dashboard_uses_membership_and_cache_per_actor() -> None:
    member = make_user(UserRole.proj_member, username="member")
    other_member = make_user(UserRole.proj_member, username="other-member")
    main_project = make_main_project(dept_id=uuid4(), status=MainProjectStatus.in_progress)
    visible_sub = make_sub_project(
        main_project=main_project,
        manager_id=uuid4(),
        status=SubProjectStatus.in_progress,
    )
    hidden_sub = make_sub_project(
        main_project=main_project,
        manager_id=uuid4(),
        status=SubProjectStatus.in_progress,
    )
    now = datetime.now(UTC)
    membership = SubProjectMember(
        id=uuid4(),
        sub_project_id=visible_sub.id,
        user_id=member.id,
        role_in_project=SubProjectMemberRole.proj_member,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )
    visible_task, visible_executor = make_task(
        sub_project_id=visible_sub.id,
        user_id=member.id,
        plan_end_date=date(2026, 5, 11),
    )
    hidden_task, hidden_executor = make_task(
        sub_project_id=hidden_sub.id,
        user_id=other_member.id,
        plan_end_date=date(2026, 5, 11),
    )
    repository = InMemoryDashboardRepository(
        DashboardSnapshot(
            users=[member, other_member],
            main_projects=[main_project],
            sub_projects=[visible_sub, hidden_sub],
            sub_project_members=[membership],
            tasks=[visible_task, hidden_task],
            task_executors=[visible_executor, hidden_executor],
            phases=[],
            payments=[],
        ),
    )
    cache = InMemoryDashboardCache()
    service = DashboardService(
        repository=repository,
        cache=cache,
        today_provider=lambda: date(2026, 5, 10),
    )

    first = await service.get_dashboard(actor=member, role_scope=UserRole.proj_member)
    second = await service.get_dashboard(actor=member, role_scope=UserRole.proj_member)

    assert repository.load_count == 1
    assert first == second
    assert cache.last_ttl_seconds == CACHE_TTL_SECONDS
    assert cache.last_key == f"dashboard:proj_member:{member.id}"
    assert first["metrics"]["todo_tasks"] == 1
    assert first["lists"]["participating_sub_projects"] == [
        {"id": str(visible_sub.id), "name": "sub", "status": "in_progress"},
    ]
