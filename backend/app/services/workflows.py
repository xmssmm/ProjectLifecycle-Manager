from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ResourceConflictError, ResourceNotFoundError
from app.models.project_types import ProjectType
from app.models.users import User
from app.models.workflows import WorkflowTemplate, WorkflowTemplateStatus, WorkflowTemplateVersion
from app.schemas.workflows import (
    ProjectTypeCreate,
    WorkflowPhaseDefinitionsUpdate,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter

WorkflowEntity = ProjectType | WorkflowTemplate | WorkflowTemplateVersion


class WorkflowRepository(Protocol):
    async def list_project_types(self) -> list[ProjectType]:
        ...

    async def get_project_type(self, project_type_id: UUID) -> ProjectType | None:
        ...

    async def get_project_type_by_code(self, code: str) -> ProjectType | None:
        ...

    def add_project_type(self, project_type: ProjectType) -> None:
        ...

    async def list_templates(self) -> list[WorkflowTemplate]:
        ...

    def add_template(self, template: WorkflowTemplate) -> None:
        ...

    async def next_template_version_no(self, template_id: UUID) -> int:
        ...

    def add_template_version(self, version: WorkflowTemplateVersion) -> None:
        ...

    async def get_template_version(self, version_id: UUID) -> WorkflowTemplateVersion | None:
        ...

    async def flush(self) -> None:
        ...

    async def commit(self) -> None:
        ...


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_project_types(self) -> list[ProjectType]:
        result = await self._session.scalars(select(ProjectType).order_by(ProjectType.code))
        return list(result.all())

    async def get_project_type(self, project_type_id: UUID) -> ProjectType | None:
        project_type = await self._session.get(ProjectType, project_type_id)
        return project_type if isinstance(project_type, ProjectType) else None

    async def get_project_type_by_code(self, code: str) -> ProjectType | None:
        project_type = await self._session.scalar(
            select(ProjectType).where(ProjectType.code == code),
        )
        return project_type if isinstance(project_type, ProjectType) else None

    def add_project_type(self, project_type: ProjectType) -> None:
        self._session.add(project_type)

    async def list_templates(self) -> list[WorkflowTemplate]:
        result = await self._session.scalars(
            select(WorkflowTemplate)
            .options(selectinload(WorkflowTemplate.versions))
            .order_by(WorkflowTemplate.created_at.desc()),
        )
        return list(result.all())

    def add_template(self, template: WorkflowTemplate) -> None:
        self._session.add(template)

    async def next_template_version_no(self, template_id: UUID) -> int:
        max_version = await self._session.scalar(
            select(func.max(WorkflowTemplateVersion.version_no)).where(
                WorkflowTemplateVersion.template_id == template_id,
            ),
        )
        return int(max_version or 0) + 1

    def add_template_version(self, version: WorkflowTemplateVersion) -> None:
        self._session.add(version)

    async def get_template_version(self, version_id: UUID) -> WorkflowTemplateVersion | None:
        version = await self._session.get(WorkflowTemplateVersion, version_id)
        return version if isinstance(version, WorkflowTemplateVersion) else None

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()


class InMemoryWorkflowRepository:
    def __init__(self, *, now_provider: Callable[[], datetime] | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self.project_types_by_id: dict[UUID, ProjectType] = {}
        self.project_types_by_code: dict[str, ProjectType] = {}
        self.templates_by_id: dict[UUID, WorkflowTemplate] = {}
        self.versions_by_id: dict[UUID, WorkflowTemplateVersion] = {}

    async def list_project_types(self) -> list[ProjectType]:
        return sorted(self.project_types_by_id.values(), key=lambda item: item.code)

    async def get_project_type(self, project_type_id: UUID) -> ProjectType | None:
        return self.project_types_by_id.get(project_type_id)

    async def get_project_type_by_code(self, code: str) -> ProjectType | None:
        return self.project_types_by_code.get(code)

    def add_project_type(self, project_type: ProjectType) -> None:
        self._stamp_entity(project_type)
        self.project_types_by_id[project_type.id] = project_type
        self.project_types_by_code[project_type.code] = project_type

    async def list_templates(self) -> list[WorkflowTemplate]:
        return sorted(self.templates_by_id.values(), key=lambda item: item.created_at, reverse=True)

    def add_template(self, template: WorkflowTemplate) -> None:
        self._stamp_entity(template)
        self.templates_by_id[template.id] = template

    async def next_template_version_no(self, template_id: UUID) -> int:
        version_numbers = [
            version.version_no
            for version in self.versions_by_id.values()
            if version.template_id == template_id
        ]
        return max(version_numbers, default=0) + 1

    def add_template_version(self, version: WorkflowTemplateVersion) -> None:
        self._stamp_entity(version)
        self.versions_by_id[version.id] = version
        template = self.templates_by_id.get(version.template_id)
        if template is not None:
            template.versions.append(version)

    async def get_template_version(self, version_id: UUID) -> WorkflowTemplateVersion | None:
        return self.versions_by_id.get(version_id)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    def _stamp_entity(self, entity: WorkflowEntity) -> None:
        entity.id = entity.id or uuid4()
        now = self._now_provider()
        entity.created_at = entity.created_at or now
        entity.updated_at = now


class WorkflowService:
    def __init__(
        self,
        *,
        repository: WorkflowRepository,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_project_types(self) -> list[ProjectType]:
        return await self._repository.list_project_types()

    async def list_templates(self) -> list[WorkflowTemplate]:
        return await self._repository.list_templates()

    async def create_project_type(
        self,
        *,
        actor: User,
        payload: ProjectTypeCreate,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> ProjectType:
        existing = await self._repository.get_project_type_by_code(payload.code)
        if existing is not None:
            raise ResourceConflictError("项目类型 code 已存在")

        project_type = ProjectType(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_builtin=False,
            is_active=True,
        )
        self._repository.add_project_type(project_type)
        await self._repository.commit()
        self._write_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="workflow.project_type.create",
            target_type="project_type",
            target_id=str(project_type.id),
            after_state={
                "code": project_type.code,
                "name": project_type.name,
                "description": project_type.description,
            },
        )
        return project_type

    async def create_template(
        self,
        *,
        actor: User,
        project_type_id: UUID,
        name: str,
        description: str | None,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> WorkflowTemplate:
        project_type = await self._repository.get_project_type(project_type_id)
        if project_type is None:
            raise ResourceNotFoundError("项目类型不存在")

        template = WorkflowTemplate(
            project_type_id=project_type_id,
            name=name,
            description=description,
            status=WorkflowTemplateStatus.draft,
            created_by_id=actor.id,
        )
        self._repository.add_template(template)
        await self._repository.flush()
        version_no = await self._repository.next_template_version_no(template.id)
        version = WorkflowTemplateVersion(
            template_id=template.id,
            version_no=version_no,
            status=WorkflowTemplateStatus.draft,
            phase_definitions=[],
            published_at=None,
        )
        self._repository.add_template_version(version)
        await self._repository.commit()
        self._write_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="workflow.template.create",
            target_type="workflow_template",
            target_id=str(template.id),
            after_state={"name": template.name, "project_type_id": str(project_type_id)},
        )
        return template

    async def update_phase_definitions(
        self,
        *,
        actor: User,
        version_id: UUID,
        payload: WorkflowPhaseDefinitionsUpdate,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> WorkflowTemplateVersion:
        version = await self._get_version_or_raise(version_id)
        before_state: dict[str, object] = {"phase_definitions": version.phase_definitions}
        version.replace_phase_definitions(
            [phase.model_dump() for phase in payload.phase_definitions],
        )
        await self._repository.commit()
        self._write_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="workflow.version.update_phase_definitions",
            target_type="workflow_template_version",
            target_id=str(version.id),
            before_state=before_state,
            after_state={"phase_definitions": version.phase_definitions},
        )
        return version

    async def publish_template_version(
        self,
        *,
        actor: User,
        version_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> WorkflowTemplateVersion:
        version = await self._get_version_or_raise(version_id)
        if version.status != WorkflowTemplateStatus.draft:
            raise ResourceConflictError("只有草稿工作流版本可以发布")
        if not version.phase_definitions:
            raise ResourceConflictError("工作流版本至少需要一个环节才能发布")

        before_state: dict[str, object] = {
            "status": version.status.value,
            "published_at": version.published_at,
        }
        version.status = WorkflowTemplateStatus.published
        version.published_at = self._now_provider()
        await self._repository.commit()
        self._write_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="workflow.version.publish",
            target_type="workflow_template_version",
            target_id=str(version.id),
            before_state=before_state,
            after_state={"status": version.status.value, "published_at": version.published_at},
        )
        return version

    async def _get_version_or_raise(self, version_id: UUID) -> WorkflowTemplateVersion:
        version = await self._repository.get_template_version(version_id)
        if version is None:
            raise ResourceNotFoundError("工作流模板版本不存在")
        return version

    @staticmethod
    def _write_audit(
        *,
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
        actor: User,
        action: str,
        target_type: str,
        target_id: str,
        before_state: dict[str, object] | None = None,
        after_state: dict[str, object] | None = None,
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id or actor.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                before_state=before_state or {},
                after_state=after_state or {},
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={},
                request_id=context.request_id,
            ),
        )
