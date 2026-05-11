from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.main_projects import MainProject
from app.models.project_types import ProjectType
from app.models.sub_projects import SubProject
from app.models.workflows import WorkflowTemplate, WorkflowTemplateStatus, WorkflowTemplateVersion
from app.schemas.workflows import WorkflowTemplateVersionCreate
from app.seeds.phase_doc_templates import PHASE_DOC_TEMPLATES

DEFAULT_PROCUREMENT_PROJECT_TYPE_CODE = "procurement"
DEFAULT_PROCUREMENT_TEMPLATE_NAME = "procurement-default"

PROCUREMENT_PHASE_NAMES: Mapping[int, tuple[str, str]] = {
    1: ("initiation", "立项准备"),
    2: ("procurement", "采购实施"),
    3: ("contract", "合同签订"),
    4: ("acceptance", "验收"),
    5: ("payment", "付款"),
    6: ("post_review", "后评价"),
}


class WorkflowSeedRepository(Protocol):
    async def get_project_type_by_code(self, code: str) -> ProjectType | None:
        ...

    def add_project_type(self, project_type: ProjectType) -> None:
        ...

    async def get_template_by_name(
        self,
        *,
        project_type_id: UUID,
        name: str,
    ) -> WorkflowTemplate | None:
        ...

    def add_template(self, template: WorkflowTemplate) -> None:
        ...

    async def get_template_version(
        self,
        *,
        template_id: UUID,
        version_no: int,
    ) -> WorkflowTemplateVersion | None:
        ...

    def add_template_version(self, version: WorkflowTemplateVersion) -> None:
        ...

    async def backfill_legacy_project_links(
        self,
        *,
        project_type_id: UUID,
        workflow_template_version_id: UUID,
    ) -> int:
        ...

    async def flush(self) -> None:
        ...


class SqlAlchemyWorkflowSeedRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_type_by_code(self, code: str) -> ProjectType | None:
        project_type = await self._session.scalar(
            select(ProjectType).where(ProjectType.code == code),
        )
        return project_type if isinstance(project_type, ProjectType) else None

    def add_project_type(self, project_type: ProjectType) -> None:
        self._session.add(project_type)

    async def get_template_by_name(
        self,
        *,
        project_type_id: UUID,
        name: str,
    ) -> WorkflowTemplate | None:
        template = await self._session.scalar(
            select(WorkflowTemplate).where(
                WorkflowTemplate.project_type_id == project_type_id,
                WorkflowTemplate.name == name,
            ),
        )
        return template if isinstance(template, WorkflowTemplate) else None

    def add_template(self, template: WorkflowTemplate) -> None:
        self._session.add(template)

    async def get_template_version(
        self,
        *,
        template_id: UUID,
        version_no: int,
    ) -> WorkflowTemplateVersion | None:
        version = await self._session.scalar(
            select(WorkflowTemplateVersion).where(
                WorkflowTemplateVersion.template_id == template_id,
                WorkflowTemplateVersion.version_no == version_no,
            ),
        )
        return version if isinstance(version, WorkflowTemplateVersion) else None

    def add_template_version(self, version: WorkflowTemplateVersion) -> None:
        self._session.add(version)

    async def backfill_legacy_project_links(
        self,
        *,
        project_type_id: UUID,
        workflow_template_version_id: UUID,
    ) -> int:
        main_result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(MainProject)
                .where(MainProject.project_type_id.is_(None))
                .values(project_type_id=project_type_id),
            ),
        )
        sub_result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(SubProject)
                .where(SubProject.workflow_template_version_id.is_(None))
                .values(workflow_template_version_id=workflow_template_version_id),
            ),
        )
        return int(main_result.rowcount or 0) + int(sub_result.rowcount or 0)

    async def flush(self) -> None:
        await self._session.flush()


def build_procurement_phase_definitions() -> list[dict[str, object]]:
    definitions: list[dict[str, object]] = []
    for phase_no in sorted(PROCUREMENT_PHASE_NAMES):
        phase_key, phase_name = PROCUREMENT_PHASE_NAMES[phase_no]
        required_documents = [
            {
                "doc_type": template.doc_type,
                "requirement": template.requirement.value,
                "qty_rule": template.qty_rule,
                "procurement_type": (
                    template.procurement_type.value
                    if template.procurement_type is not None
                    else None
                ),
            }
            for template in PHASE_DOC_TEMPLATES
            if template.phase_no == phase_no
        ]
        definitions.append(
            {
                "key": phase_key,
                "name": phase_name,
                "order": phase_no,
                "required_documents": required_documents,
                "allow_parallel": False,
                "entry_rules": {},
            },
        )
    payload = WorkflowTemplateVersionCreate.model_validate({"phase_definitions": definitions})
    return [phase.model_dump() for phase in payload.phase_definitions]


async def seed_default_procurement_workflow(repository: WorkflowSeedRepository) -> int:
    inserted = 0
    project_type = await repository.get_project_type_by_code(DEFAULT_PROCUREMENT_PROJECT_TYPE_CODE)
    if project_type is None:
        project_type = ProjectType(
            code=DEFAULT_PROCUREMENT_PROJECT_TYPE_CODE,
            name="采购项目",
            description="系统内置采购项目类型，兼容既有 6 环节流程。",
            is_builtin=True,
            is_active=True,
        )
        repository.add_project_type(project_type)
        await repository.flush()
        inserted += 1

    template = await repository.get_template_by_name(
        project_type_id=project_type.id,
        name=DEFAULT_PROCUREMENT_TEMPLATE_NAME,
    )
    if template is None:
        template = WorkflowTemplate(
            project_type_id=project_type.id,
            name=DEFAULT_PROCUREMENT_TEMPLATE_NAME,
            description="系统内置采购流程模板。",
            status=WorkflowTemplateStatus.published,
            created_by_id=None,
        )
        repository.add_template(template)
        await repository.flush()
        inserted += 1

    version = await repository.get_template_version(template_id=template.id, version_no=1)
    if version is None:
        version = WorkflowTemplateVersion(
            template_id=template.id,
            version_no=1,
            status=WorkflowTemplateStatus.published,
            phase_definitions=build_procurement_phase_definitions(),
            published_at=datetime.now(UTC),
        )
        repository.add_template_version(version)
        await repository.flush()
        inserted += 1

    inserted += await repository.backfill_legacy_project_links(
        project_type_id=project_type.id,
        workflow_template_version_id=version.id,
    )

    return inserted


async def seed_workflow_templates(session: AsyncSession) -> int:
    return await seed_default_procurement_workflow(SqlAlchemyWorkflowSeedRepository(session))
