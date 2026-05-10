from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.tasks import Task, TaskStatus
from app.models.users import User
from app.schemas.tasks import TaskCreate, TaskListRead, TaskRead, TaskUpdate
from app.services.notifications import NotificationService, SqlAlchemyNotificationRepository
from app.services.tasks import SqlAlchemyTaskRepository, TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def get_task_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskService:
    return TaskService(
        repository=SqlAlchemyTaskRepository(session),
        notification_service=NotificationService(
            repository=SqlAlchemyNotificationRepository(session),
        ),
    )


def serialize_task(task: Task) -> dict[str, object]:
    return TaskRead.model_validate(task).model_dump(mode="json")


@router.get("", summary="List tasks")
async def list_tasks(
    service: Annotated[TaskService, Depends(get_task_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    sub_project_id: Annotated[UUID | None, Query()] = None,
    assignee: Annotated[str | None, Query(description="Use assignee=me for current user")] = None,
    status: Annotated[TaskStatus | None, Query()] = None,
) -> dict[str, object]:
    tasks = await service.list_tasks(
        actor=current_user,
        sub_project_id=sub_project_id,
        assignee=assignee,
        status=status,
    )
    payload = TaskListRead(
        items=[TaskRead.model_validate(task) for task in tasks],
        total=len(tasks),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("", summary="Create and assign a task")
async def create_task(
    payload: TaskCreate,
    service: Annotated[TaskService, Depends(get_task_service)],
    current_user: Annotated[User, Depends(require_permission("task.assign"))],
) -> dict[str, object]:
    task = await service.create_task(actor=current_user, payload=payload)
    return success_response(serialize_task(task))


@router.get("/{task_id}", summary="Get task detail")
async def get_task(
    task_id: UUID,
    service: Annotated[TaskService, Depends(get_task_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    task = await service.get_task(actor=current_user, task_id=task_id)
    return success_response(serialize_task(task))


@router.put("/{task_id}", summary="Update task and assignees")
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    service: Annotated[TaskService, Depends(get_task_service)],
    current_user: Annotated[User, Depends(require_permission("task.assign"))],
) -> dict[str, object]:
    task = await service.update_task(actor=current_user, task_id=task_id, payload=payload)
    return success_response(serialize_task(task))


@router.post("/{task_id}/complete", summary="Complete current user's task executor record")
async def complete_task(
    task_id: UUID,
    service: Annotated[TaskService, Depends(get_task_service)],
    current_user: Annotated[User, Depends(require_permission("task.complete"))],
) -> dict[str, object]:
    task = await service.complete_task(actor=current_user, task_id=task_id)
    return success_response(serialize_task(task))
