from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.project_taxonomy import (
    ProjectCategory,
    ProjectTag,
    ProjectTemplate,
    ProjectTemplateScope,
)
from app.models.users import User, UserRole
from app.schemas.project_taxonomy import (
    ProjectCategoryCreate,
    ProjectTagCreate,
    ProjectTemplateCreateFromProject,
    ProjectTemplateInstantiate,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter, to_audit_state


class ProjectTemplateRepository(Protocol):
    async def list_categories(self) -> list[ProjectCategory]: ...

    async def list_tags(self) -> list[ProjectTag]: ...

    async def list_templates(self) -> list[ProjectTemplate]: ...

    async def get_project(self, project_id: UUID) -> MainProject | None: ...

    async def get_template(self, template_id: UUID) -> ProjectTemplate | None: ...

    async def next_project_sequence(self) -> int: ...

    def add_category(self, category: ProjectCategory) -> None: ...

    def add_tag(self, tag: ProjectTag) -> None: ...

    def add_template(self, template: ProjectTemplate) -> None: ...

    def add_project(self, project: MainProject) -> None: ...

    async def commit(self) -> None: ...

    async def refresh(self, entity: object) -> None: ...


class SqlAlchemyProjectTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_categories(self) -> list[ProjectCategory]:
        result = await self._session.scalars(
            select(ProjectCategory)
            .where(ProjectCategory.is_active.is_(True))
            .order_by(ProjectCategory.name),
        )
        return list(result.all())

    async def list_tags(self) -> list[ProjectTag]:
        result = await self._session.scalars(
            select(ProjectTag).where(ProjectTag.is_active.is_(True)).order_by(ProjectTag.name),
        )
        return list(result.all())

    async def list_templates(self) -> list[ProjectTemplate]:
        result = await self._session.scalars(
            select(ProjectTemplate)
            .where(ProjectTemplate.is_active.is_(True))
            .order_by(ProjectTemplate.created_at.desc()),
        )
        return list(result.all())

    async def get_project(self, project_id: UUID) -> MainProject | None:
        project = await self._session.get(MainProject, project_id)
        return project if isinstance(project, MainProject) else None

    async def get_template(self, template_id: UUID) -> ProjectTemplate | None:
        template = await self._session.get(ProjectTemplate, template_id)
        if template is None or not template.is_active:
            return None
        return template

    async def next_project_sequence(self) -> int:
        value = await self._session.scalar(text("SELECT nextval('main_project_no_seq')"))
        return int(value or 1)

    def add_category(self, category: ProjectCategory) -> None:
        self._session.add(category)

    def add_tag(self, tag: ProjectTag) -> None:
        self._session.add(tag)

    def add_template(self, template: ProjectTemplate) -> None:
        self._session.add(template)

    def add_project(self, project: MainProject) -> None:
        self._session.add(project)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, entity: object) -> None:
        await self._session.refresh(entity)


class InMemoryProjectTemplateRepository:
    def __init__(
        self,
        *,
        categories: Sequence[ProjectCategory] | None = None,
        projects: Sequence[MainProject] | None = None,
        tags: Sequence[ProjectTag] | None = None,
        templates: Sequence[ProjectTemplate] | None = None,
        users: Sequence[User] | None = None,
        next_project_sequence: int = 1,
    ) -> None:
        self.categories = list(categories or [])
        self.projects = list(projects or [])
        self.tags = list(tags or [])
        self.templates = list(templates or [])
        self.users = list(users or [])
        self._next_project_sequence = next_project_sequence

    async def list_categories(self) -> list[ProjectCategory]:
        return sorted(
            [item for item in self.categories if item.is_active],
            key=lambda item: item.name,
        )

    async def list_tags(self) -> list[ProjectTag]:
        return sorted([item for item in self.tags if item.is_active], key=lambda item: item.name)

    async def list_templates(self) -> list[ProjectTemplate]:
        return sorted(
            [item for item in self.templates if item.is_active],
            key=lambda item: item.created_at,
            reverse=True,
        )

    async def get_project(self, project_id: UUID) -> MainProject | None:
        return next((project for project in self.projects if project.id == project_id), None)

    async def get_template(self, template_id: UUID) -> ProjectTemplate | None:
        return next(
            (
                template
                for template in self.templates
                if template.id == template_id and template.is_active
            ),
            None,
        )

    async def next_project_sequence(self) -> int:
        value = self._next_project_sequence
        self._next_project_sequence += 1
        return value

    def add_category(self, category: ProjectCategory) -> None:
        self.categories.append(category)

    def add_tag(self, tag: ProjectTag) -> None:
        self.tags.append(tag)

    def add_template(self, template: ProjectTemplate) -> None:
        self.templates.append(template)

    def add_project(self, project: MainProject) -> None:
        self.projects.append(project)

    async def commit(self) -> None:
        return None

    async def refresh(self, entity: object) -> None:
        _ = entity


class ProjectTemplateService:
    def __init__(
        self,
        *,
        repository: ProjectTemplateRepository,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._now_provider = now_provider
        self._today_provider = today_provider

    async def list_categories(self) -> list[ProjectCategory]:
        return await self._repository.list_categories()

    async def list_tags(self) -> list[ProjectTag]:
        return await self._repository.list_tags()

    async def create_category(
        self,
        *,
        actor: User,
        payload: ProjectCategoryCreate,
    ) -> ProjectCategory:
        self._ensure_admin(actor)
        now = self._now_provider()
        category = ProjectCategory(
            id=uuid4(),
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_category(category)
        await self._repository.commit()
        await self._repository.refresh(category)
        return category

    async def create_tag(self, *, actor: User, payload: ProjectTagCreate) -> ProjectTag:
        self._ensure_admin(actor)
        now = self._now_provider()
        tag = ProjectTag(
            id=uuid4(),
            code=payload.code,
            name=payload.name,
            color=payload.color,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_tag(tag)
        await self._repository.commit()
        await self._repository.refresh(tag)
        return tag

    async def list_templates(
        self,
        *,
        actor: User,
        tag_id: UUID | None = None,
    ) -> list[ProjectTemplate]:
        templates = await self._repository.list_templates()
        return [
            template
            for template in templates
            if self._can_view(actor, template)
            if tag_id is None or str(tag_id) in template.tag_ids
        ]

    async def create_template_from_project(
        self,
        *,
        actor: User,
        payload: ProjectTemplateCreateFromProject,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> ProjectTemplate:
        self._ensure_template_scope_allowed(actor, payload.scope)
        source = await self._get_source_project(payload.source_project_id)
        now = self._now_provider()
        template = ProjectTemplate(
            id=uuid4(),
            name=payload.name,
            description=payload.description,
            scope=payload.scope,
            owner_id=actor.id,
            owner_dept_id=actor.dept_id,
            source_project_id=source.id,
            source_project_no=source.project_no,
            category_id=payload.category_id,
            project_type_id=source.project_type_id,
            tag_ids=[str(tag_id) for tag_id in payload.tag_ids],
            field_defaults=self._field_defaults(source),
            phase_snapshot=[] if not payload.copy_phase_plan else self._phase_snapshot(source),
            document_requirements_snapshot=(
                [] if not payload.copy_document_requirements else self._document_snapshot(source)
            ),
            default_task_checklist=(
                [] if not payload.copy_task_checklist else self._task_snapshot(source)
            ),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_template(template)
        await self._repository.commit()
        await self._repository.refresh(template)
        self._record_audit(
            action="project_template.create",
            actor=actor,
            target_type="project_template",
            target_id=str(template.id),
            after_state=to_audit_state(template),
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={"source_project_id": str(source.id)},
        )
        return template

    async def instantiate_template(
        self,
        *,
        actor: User,
        template_id: UUID,
        payload: ProjectTemplateInstantiate,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> MainProject:
        if actor.role != UserRole.dept_manager and actor.role != UserRole.admin:
            raise PermissionDeniedError()
        template = await self._get_visible_template(actor=actor, template_id=template_id)
        defaults = template.field_defaults
        now = self._now_provider()
        sequence = await self._repository.next_project_sequence()
        project = MainProject(
            id=uuid4(),
            project_no=self._format_project_no(sequence),
            name=payload.name or str(defaults.get("name") or template.name),
            dept_id=payload.dept_id or actor.dept_id,
            status=MainProjectStatus.pending_review,
            total_budget=payload.total_budget or Decimal(str(defaults.get("total_budget", "0"))),
            expected_finish_date=payload.expected_finish_date
            or date.fromisoformat(str(defaults["expected_finish_date"])),
            spent_amount=Decimal("0.00"),
            remark=payload.remark if payload.remark is not None else defaults.get("remark"),
            creator_id=actor.id,
            project_type_id=template.project_type_id,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_project(project)
        await self._repository.commit()
        await self._repository.refresh(project)
        self._record_audit(
            action="project_template.instantiate",
            actor=actor,
            target_type="main_project",
            target_id=str(project.id),
            after_state=to_audit_state(project),
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={"project_template_id": str(template.id), "project_template_name": template.name},
        )
        return project

    async def _get_source_project(self, project_id: UUID) -> MainProject:
        project = await self._repository.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError("Source project does not exist")
        return project

    async def _get_visible_template(self, *, actor: User, template_id: UUID) -> ProjectTemplate:
        template = await self._repository.get_template(template_id)
        if template is None:
            raise ResourceNotFoundError("Project template does not exist")
        if not self._can_view(actor, template):
            raise PermissionDeniedError()
        return template

    @staticmethod
    def _ensure_admin(actor: User) -> None:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()

    @staticmethod
    def _ensure_template_scope_allowed(actor: User, scope: ProjectTemplateScope) -> None:
        if scope == ProjectTemplateScope.global_ and actor.role != UserRole.admin:
            raise PermissionDeniedError()
        if scope == ProjectTemplateScope.department and actor.role not in {
            UserRole.admin,
            UserRole.dept_manager,
        }:
            raise PermissionDeniedError()

    @staticmethod
    def _can_view(actor: User, template: ProjectTemplate) -> bool:
        if actor.role == UserRole.admin or template.owner_id == actor.id:
            return True
        if template.scope == ProjectTemplateScope.global_:
            return True
        return (
            template.scope == ProjectTemplateScope.department
            and actor.dept_id is not None
            and actor.dept_id == template.owner_dept_id
        )

    @staticmethod
    def _field_defaults(project: MainProject) -> dict[str, object]:
        return {
            "expected_finish_date": project.expected_finish_date.isoformat(),
            "name": project.name,
            "remark": project.remark,
            "total_budget": str(project.total_budget),
        }

    @staticmethod
    def _phase_snapshot(project: MainProject) -> list[dict[str, object]]:
        _ = project
        return []

    @staticmethod
    def _document_snapshot(project: MainProject) -> list[dict[str, object]]:
        _ = project
        return []

    @staticmethod
    def _task_snapshot(project: MainProject) -> list[dict[str, object]]:
        _ = project
        return []

    @staticmethod
    def _record_audit(
        *,
        action: str,
        actor: User,
        target_type: str,
        target_id: str,
        after_state: Mapping[str, object],
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
        before_state: Mapping[str, object] | None = None,
        extra: Mapping[str, object] | None = None,
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
                before_state=dict(before_state or {}),
                after_state=dict(after_state),
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra=dict(extra or {}),
                request_id=context.request_id,
            ),
        )

    def _format_project_no(self, sequence_value: int) -> str:
        return f"Z-{self._today_provider().year}-{sequence_value:04d}"
