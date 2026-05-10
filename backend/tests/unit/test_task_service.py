from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.tasks import get_task_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.tasks import Task, TaskExecutor, TaskStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.tasks import TaskCreate, TaskExecutorAssign, TaskUpdate
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.tasks import InMemoryTaskRepository, TaskService


def make_user(role: UserRole, *, username: str) -> User:
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


def make_sub_project(manager: User) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no="Z-2026-0001-ZX-001",
        name="Implementation",
        main_project_id=uuid4(),
        dept_id=uuid4(),
        budget=Decimal("100000.00"),
        manager_id=manager.id,
        creator_id=manager.id,
        status=SubProjectStatus.in_progress,
        plan_end_date=date(2026, 12, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark=None,
        created_at=now,
        updated_at=now,
    )


def make_phase(sub_project: SubProject) -> Phase:
    now = datetime.now(UTC)
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=1,
        code="initiation",
        name="Initiation",
        status=PhaseStatus.in_progress,
        enter_at=now,
        finish_at=None,
        procurement_type=None,
        created_at=now,
        updated_at=now,
    )


def make_member(
    sub_project: SubProject,
    user: User,
    role: SubProjectMemberRole = SubProjectMemberRole.proj_member,
) -> SubProjectMember:
    now = datetime.now(UTC)
    return SubProjectMember(
        id=uuid4(),
        sub_project_id=sub_project.id,
        user_id=user.id,
        role_in_project=role,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )


def make_task(sub_project: SubProject, phase: Phase, *, sequence: int = 1) -> Task:
    now = datetime.now(UTC)
    return Task(
        id=uuid4(),
        task_no=f"{sub_project.project_no}-T-{sequence:03d}",
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        name="Prepare minutes",
        plan_end_date=date(2026, 5, 20),
        status=TaskStatus.in_progress,
        created_at=now,
        updated_at=now,
    )


def make_executor(
    task: Task,
    user: User,
    *,
    status: TaskStatus = TaskStatus.in_progress,
    plan_end_date: date = date(2026, 5, 20),
) -> TaskExecutor:
    now = datetime.now(UTC)
    return TaskExecutor(
        id=uuid4(),
        task_id=task.id,
        user_id=user.id,
        plan_end_date=plan_end_date,
        actual_end_date=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


def make_service(
    *,
    tasks: list[Task] | None = None,
    executors: list[TaskExecutor] | None = None,
    phases: list[Phase],
    sub_projects: list[SubProject],
    members: list[SubProjectMember],
) -> tuple[TaskService, InMemoryTaskRepository, InMemoryNotificationRepository]:
    repository = InMemoryTaskRepository(
        tasks=tasks or [],
        executors=executors or [],
        phases=phases,
        sub_projects=sub_projects,
        members=members,
    )
    notification_repository = InMemoryNotificationRepository()
    service = TaskService(
        repository=repository,
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: date(2026, 5, 10),
        ),
        today_provider=lambda: date(2026, 5, 10),
    )
    return service, repository, notification_repository


@pytest.mark.asyncio
async def test_create_task_assigns_multiple_members_and_notifies_each_executor() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member_a = make_user(UserRole.proj_member, username="member-a")
    member_b = make_user(UserRole.proj_member, username="member-b")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    service, repository, notifications = make_service(
        phases=[phase],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member_a),
            make_member(sub_project, member_b),
        ],
    )

    task = await service.create_task(
        actor=leader,
        payload=TaskCreate(
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            name="Prepare minutes",
            plan_end_date=date(2026, 5, 22),
            executors=[
                TaskExecutorAssign(user_id=member_a.id, plan_end_date=date(2026, 5, 20)),
                TaskExecutorAssign(user_id=member_b.id, plan_end_date=date(2026, 5, 21)),
            ],
        ),
    )

    assert task.task_no == "Z-2026-0001-ZX-001-T-001"
    assert task.status == TaskStatus.in_progress
    assert task in repository.tasks
    assert {executor.user_id for executor in task.executors} == {member_a.id, member_b.id}
    assert all(executor.status == TaskStatus.in_progress for executor in task.executors)
    assert [item.receiver_id for item in notifications.notifications] == [member_a.id, member_b.id]
    assert {item.scenario for item in notifications.notifications} == {"task_assigned"}
    assert {item.source_id for item in notifications.notifications} == {str(task.id)}


@pytest.mark.asyncio
async def test_create_task_requires_project_leader_and_sub_project_members() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member = make_user(UserRole.proj_member, username="member")
    outsider = make_user(UserRole.proj_member, username="outsider")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    service, _repository, _notifications = make_service(
        phases=[phase],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member),
        ],
    )
    payload = TaskCreate(
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        name="Prepare minutes",
        plan_end_date=date(2026, 5, 22),
        executors=[TaskExecutorAssign(user_id=member.id, plan_end_date=date(2026, 5, 20))],
    )

    with pytest.raises(PermissionDeniedError):
        await service.create_task(actor=member, payload=payload)

    invalid_executor_payload = payload.model_copy(
        update={
            "executors": [
                TaskExecutorAssign(user_id=outsider.id, plan_end_date=date(2026, 5, 20)),
            ],
        },
    )
    with pytest.raises(BusinessException) as invalid_executor:
        await service.create_task(actor=leader, payload=invalid_executor_payload)
    assert invalid_executor.value.code == 3003


@pytest.mark.asyncio
async def test_update_task_replaces_assignees_preserves_existing_status_and_notifies_new() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member_a = make_user(UserRole.proj_member, username="member-a")
    member_b = make_user(UserRole.proj_member, username="member-b")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    task = make_task(sub_project, phase)
    executor_a = make_executor(task, member_a, status=TaskStatus.completed)
    task.executors = [executor_a]
    service, repository, notifications = make_service(
        tasks=[task],
        executors=[executor_a],
        phases=[phase],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member_a),
            make_member(sub_project, member_b),
        ],
    )

    updated = await service.update_task(
        actor=leader,
        task_id=task.id,
        payload=TaskUpdate(
            name="Prepare and review minutes",
            plan_end_date=date(2026, 5, 25),
            executors=[
                TaskExecutorAssign(user_id=member_a.id, plan_end_date=date(2026, 5, 24)),
                TaskExecutorAssign(user_id=member_b.id, plan_end_date=date(2026, 5, 25)),
            ],
        ),
    )

    assert updated.name == "Prepare and review minutes"
    assert updated.plan_end_date == date(2026, 5, 25)
    assert updated.status == TaskStatus.in_progress
    assert {executor.user_id for executor in updated.executors} == {member_a.id, member_b.id}
    existing = next(executor for executor in updated.executors if executor.user_id == member_a.id)
    new_executor = next(
        executor for executor in updated.executors if executor.user_id == member_b.id
    )
    assert existing.status == TaskStatus.completed
    assert existing.plan_end_date == date(2026, 5, 24)
    assert new_executor.status == TaskStatus.in_progress
    assert [executor.user_id for executor in repository.executors] == [member_a.id, member_b.id]
    assert [item.receiver_id for item in notifications.notifications] == [member_b.id]


@pytest.mark.asyncio
async def test_complete_task_marks_only_actor_executor_and_aggregates_task_status() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member_a = make_user(UserRole.proj_member, username="member-a")
    member_b = make_user(UserRole.proj_member, username="member-b")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    task = make_task(sub_project, phase)
    executor_a = make_executor(task, member_a)
    executor_b = make_executor(task, member_b)
    task.executors = [executor_a, executor_b]
    service, _repository, _notifications = make_service(
        tasks=[task],
        executors=[executor_a, executor_b],
        phases=[phase],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member_a),
            make_member(sub_project, member_b),
        ],
    )

    partially_completed = await service.complete_task(actor=member_a, task_id=task.id)

    assert executor_a.status == TaskStatus.completed
    assert executor_a.actual_end_date == date(2026, 5, 10)
    assert executor_b.status == TaskStatus.in_progress
    assert partially_completed.status == TaskStatus.in_progress

    completed = await service.complete_task(actor=member_b, task_id=task.id)

    assert TaskStatus(executor_b.status) == TaskStatus.completed
    assert executor_b.actual_end_date == date(2026, 5, 10)
    assert completed.status == TaskStatus.completed


@pytest.mark.asyncio
async def test_list_and_get_tasks_enforce_visibility_and_assignee_me_filter() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member_a = make_user(UserRole.proj_member, username="member-a")
    member_b = make_user(UserRole.proj_member, username="member-b")
    outsider = make_user(UserRole.proj_member, username="outsider")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    task_a = make_task(sub_project, phase, sequence=1)
    task_b = make_task(sub_project, phase, sequence=2)
    executor_a = make_executor(task_a, member_a)
    executor_b = make_executor(task_b, member_b)
    task_a.executors = [executor_a]
    task_b.executors = [executor_b]
    service, _repository, _notifications = make_service(
        tasks=[task_a, task_b],
        executors=[executor_a, executor_b],
        phases=[phase],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member_a),
            make_member(sub_project, member_b),
        ],
    )

    visible_to_member = await service.list_tasks(
        actor=member_a,
        sub_project_id=sub_project.id,
        assignee="me",
        status=None,
    )

    assert visible_to_member == [task_a]
    assert await service.get_task(actor=member_b, task_id=task_a.id) == task_a
    with pytest.raises(PermissionDeniedError):
        await service.get_task(actor=outsider, task_id=task_a.id)


def test_task_api_routes_call_service_and_serialize_payloads() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    member = make_user(UserRole.proj_member, username="member")
    sub_project = make_sub_project(leader)
    phase = make_phase(sub_project)
    task = make_task(sub_project, phase)
    executor = make_executor(task, member)
    task.executors = [executor]

    class FakeTaskService:
        async def list_tasks(
            self,
            *,
            actor: User,
            sub_project_id: UUID | None,
            assignee: str | None,
            status: TaskStatus | None,
        ) -> list[Task]:
            assert actor.id == leader.id
            assert sub_project_id == sub_project.id
            assert assignee == "me"
            assert status == TaskStatus.in_progress
            return [task]

        async def create_task(self, *, actor: User, payload: TaskCreate) -> Task:
            assert actor.id == leader.id
            assert payload.executors[0].user_id == member.id
            return task

        async def get_task(self, *, actor: User, task_id: UUID) -> Task:
            assert actor.id == leader.id
            assert task_id == task.id
            return task

        async def update_task(self, *, actor: User, task_id: UUID, payload: TaskUpdate) -> Task:
            assert actor.id == leader.id
            assert task_id == task.id
            assert payload.name == "Updated"
            task.name = "Updated"
            return task

        async def complete_task(self, *, actor: User, task_id: UUID) -> Task:
            assert actor.id == leader.id
            assert task_id == task.id
            executor.status = TaskStatus.completed
            task.status = TaskStatus.completed
            return task

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return leader

    async def fake_task_service() -> FakeTaskService:
        return FakeTaskService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_task_service] = fake_task_service
    client = TestClient(app)

    list_response = client.get(
        f"/api/v1/tasks?sub_project_id={sub_project.id}&assignee=me&status=in_progress",
    )
    create_response = client.post(
        "/api/v1/tasks",
        json={
            "sub_project_id": str(sub_project.id),
            "phase_id": str(phase.id),
            "name": "Prepare minutes",
            "plan_end_date": "2026-05-22",
            "executors": [
                {"user_id": str(member.id), "plan_end_date": "2026-05-20"},
            ],
        },
    )
    detail_response = client.get(f"/api/v1/tasks/{task.id}")
    update_response = client.put(f"/api/v1/tasks/{task.id}", json={"name": "Updated"})
    complete_response = client.post(f"/api/v1/tasks/{task.id}/complete")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1
    assert create_response.json()["data"]["executors"][0]["user_id"] == str(member.id)
    assert detail_response.json()["data"]["id"] == str(task.id)
    assert update_response.json()["data"]["name"] == "Updated"
    assert complete_response.json()["data"]["status"] == "completed"
