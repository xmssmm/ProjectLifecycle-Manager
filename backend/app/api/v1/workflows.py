from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.project_types import ProjectType
from app.models.users import User, UserRole
from app.models.workflows import WorkflowTemplate, WorkflowTemplateVersion
from app.schemas.workflows import (
    ProjectTypeCreate,
    ProjectTypeRead,
    WorkflowPhaseDefinitionsUpdate,
    WorkflowTemplateCreate,
    WorkflowTemplateRead,
    WorkflowTemplateVersionRead,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.workflows import SqlAlchemyWorkflowRepository, WorkflowService

router = APIRouter(prefix="/workflows", tags=["workflows"])


async def get_workflow_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkflowService:
    return WorkflowService(repository=SqlAlchemyWorkflowRepository(session))


def serialize_project_type(project_type: ProjectType) -> dict[str, object]:
    return ProjectTypeRead.model_validate(project_type).model_dump(mode="json")


def serialize_template(template: WorkflowTemplate) -> dict[str, object]:
    return WorkflowTemplateRead.model_validate(template).model_dump(mode="json")


def serialize_template_version(version: WorkflowTemplateVersion) -> dict[str, object]:
    return WorkflowTemplateVersionRead.model_validate(version).model_dump(mode="json")


@router.get("/project-types")
async def list_project_types(
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    project_types = await service.list_project_types()
    return success_response([serialize_project_type(item) for item in project_types])


@router.post("/project-types")
async def create_project_type(
    payload: ProjectTypeCreate,
    background_tasks: BackgroundTasks,
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    project_type = await service.create_project_type(
        actor=current_user,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_project_type(project_type))


@router.get("/templates")
async def list_templates(
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    templates = await service.list_templates()
    return success_response([serialize_template(item) for item in templates])


@router.post("/templates")
async def create_template(
    payload: WorkflowTemplateCreate,
    background_tasks: BackgroundTasks,
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    template = await service.create_template(
        actor=current_user,
        project_type_id=payload.project_type_id,
        name=payload.name,
        description=payload.description,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_template(template))


@router.put("/template-versions/{version_id}/phase-definitions")
async def update_template_version_phase_definitions(
    version_id: UUID,
    payload: WorkflowPhaseDefinitionsUpdate,
    background_tasks: BackgroundTasks,
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    version = await service.update_phase_definitions(
        actor=current_user,
        version_id=version_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_template_version(version))


@router.post("/template-versions/{version_id}/publish")
async def publish_template_version(
    version_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[WorkflowService, Depends(get_workflow_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    version = await service.publish_template_version(
        actor=current_user,
        version_id=version_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_template_version(version))
