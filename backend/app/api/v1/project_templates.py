from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.main_projects import MainProject
from app.models.project_taxonomy import ProjectCategory, ProjectTag, ProjectTemplate
from app.models.users import User
from app.schemas.main_projects import MainProjectRead
from app.schemas.project_taxonomy import (
    ProjectCategoryCreate,
    ProjectCategoryRead,
    ProjectTagCreate,
    ProjectTagRead,
    ProjectTemplateCreateFromProject,
    ProjectTemplateInstantiate,
    ProjectTemplateRead,
)
from app.services.audit import (
    AuditContext,
    AuditLogWriter,
    BackgroundAuditLogWriter,
    get_audit_context,
)
from app.services.project_templates import (
    ProjectTemplateService,
    SqlAlchemyProjectTemplateRepository,
)

router = APIRouter(prefix="/project-templates", tags=["project-templates"])


async def get_project_template_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectTemplateService:
    return ProjectTemplateService(repository=SqlAlchemyProjectTemplateRepository(session))


def get_project_template_audit_writer(background_tasks: BackgroundTasks) -> AuditLogWriter:
    return BackgroundAuditLogWriter(
        background_tasks=background_tasks,
        session_factory=AsyncSessionLocal,
    )


@router.get("/categories")
async def list_project_categories(
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    categories = await service.list_categories()
    return success_response([serialize_category(category) for category in categories])


@router.post("/categories")
async def create_project_category(
    payload: ProjectCategoryCreate,
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    category = await service.create_category(actor=current_user, payload=payload)
    return success_response(serialize_category(category))


@router.get("/tags")
async def list_project_tags(
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    tags = await service.list_tags()
    return success_response([serialize_tag(tag) for tag in tags])


@router.post("/tags")
async def create_project_tag(
    payload: ProjectTagCreate,
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    tag = await service.create_tag(actor=current_user, payload=payload)
    return success_response(serialize_tag(tag))


@router.get("/templates")
async def list_project_templates(
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    tag_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, object]:
    templates = await service.list_templates(actor=current_user, tag_id=tag_id)
    return success_response([serialize_template(template) for template in templates])


@router.post("/templates/from-project")
async def create_project_template_from_project(
    payload: ProjectTemplateCreateFromProject,
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    audit_writer: Annotated[AuditLogWriter, Depends(get_project_template_audit_writer)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    template = await service.create_template_from_project(
        actor=current_user,
        payload=payload,
        audit_writer=audit_writer,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_template(template))


@router.post("/templates/{template_id}/instantiate")
async def instantiate_project_template(
    template_id: UUID,
    payload: ProjectTemplateInstantiate,
    service: Annotated[ProjectTemplateService, Depends(get_project_template_service)],
    audit_writer: Annotated[AuditLogWriter, Depends(get_project_template_audit_writer)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = await service.instantiate_template(
        actor=current_user,
        template_id=template_id,
        payload=payload,
        audit_writer=audit_writer,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_project(project))


def serialize_category(category: ProjectCategory) -> dict[str, object]:
    return ProjectCategoryRead.model_validate(category).model_dump(mode="json")


def serialize_tag(tag: ProjectTag) -> dict[str, object]:
    return ProjectTagRead.model_validate(tag).model_dump(mode="json")


def serialize_template(template: ProjectTemplate) -> dict[str, object]:
    return ProjectTemplateRead.model_validate(template).model_dump(mode="json")


def serialize_project(project: MainProject) -> dict[str, object]:
    return MainProjectRead.model_validate(project).model_dump(mode="json")
