from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError, ValidationFailedError
from app.models.documents import Document
from app.models.main_projects import MainProject
from app.models.phases import Phase, PhaseDocRequirement, PhaseDocTemplate, ProcurementType
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.users import User, UserRole
from app.models.workflows import WorkflowTemplateVersion
from app.services.ai_providers import (
    AiProviderDisabledError,
    AiProviderError,
    AiProviderService,
    AiSchemaValidationError,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter

VIEW_ALL_CLASSIFICATION_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)

KEYWORD_RULES: tuple[tuple[str, str, float], ...] = (
    ("合同", "contract", 0.9),
    ("contract", "contract", 0.9),
    ("协议", "contract", 0.82),
    ("验收", "acceptance_report", 0.9),
    ("acceptance", "acceptance_report", 0.86),
    ("会议纪要", "meeting_minutes", 0.88),
    ("纪要", "meeting_minutes", 0.84),
    ("会议", "meeting_material", 0.78),
    ("oa", "oa_screenshot", 0.78),
    ("截图", "oa_screenshot", 0.78),
    ("招标", "bid_document", 0.84),
    ("投标", "bid_document", 0.82),
    ("采购", "procurement_document", 0.7),
    ("发票", "invoice", 0.86),
    ("付款", "payment_voucher", 0.82),
    ("支付", "payment_voucher", 0.78),
    ("预算", "budget_document", 0.78),
    ("复盘", "post_review_report", 0.84),
)

EXTENSION_RULES: dict[str, tuple[str, float]] = {
    ".doc": ("word_document", 0.42),
    ".docx": ("word_document", 0.42),
    ".xls": ("spreadsheet", 0.42),
    ".xlsx": ("spreadsheet", 0.42),
    ".ppt": ("presentation", 0.42),
    ".pptx": ("presentation", 0.42),
    ".jpg": ("image_evidence", 0.42),
    ".jpeg": ("image_evidence", 0.42),
    ".png": ("image_evidence", 0.42),
    ".pdf": ("pdf_document", 0.38),
}


@dataclass(frozen=True)
class DocumentClassificationRequest:
    sub_project_id: UUID
    phase_id: UUID
    file_name: str
    current_doc_type: str | None = None
    document_id: UUID | None = None
    summary: str | None = None


@dataclass(frozen=True)
class DocumentTypeSuggestion:
    doc_type: str
    confidence: float
    reason: str
    source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence,
            "doc_type": self.doc_type,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True)
class DocumentClassificationResult:
    sub_project_id: UUID
    phase_id: UUID
    file_name: str
    current_doc_type: str | None
    document_id: UUID | None
    suggestions: list[DocumentTypeSuggestion]

    def to_dict(self) -> dict[str, object]:
        return {
            "current_doc_type": self.current_doc_type,
            "document_id": str(self.document_id) if self.document_id else None,
            "file_name": self.file_name,
            "phase_id": str(self.phase_id),
            "sub_project_id": str(self.sub_project_id),
            "suggestions": [item.to_dict() for item in self.suggestions],
        }


class DocumentClassificationRepository(Protocol):
    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None: ...

    async def get_phase(self, phase_id: UUID) -> Phase | None: ...

    async def get_document(self, document_id: UUID) -> Document | None: ...

    async def get_main_project(self, main_project_id: UUID) -> MainProject | None: ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def get_workflow_template_version(
        self,
        version_id: UUID,
    ) -> WorkflowTemplateVersion | None: ...

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]: ...


class SqlAlchemyDocumentClassificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.get(SubProject, sub_project_id)
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        phase = await self._session.get(Phase, phase_id)
        return phase if isinstance(phase, Phase) else None

    async def get_document(self, document_id: UUID) -> Document | None:
        document = await self._session.get(Document, document_id)
        return document if isinstance(document, Document) else None

    async def get_main_project(self, main_project_id: UUID) -> MainProject | None:
        main_project = await self._session.get(MainProject, main_project_id)
        return main_project if isinstance(main_project, MainProject) else None

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        member = await self._session.scalar(
            select(SubProjectMember).where(
                SubProjectMember.sub_project_id == sub_project_id,
                SubProjectMember.user_id == user_id,
            ),
        )
        return member if isinstance(member, SubProjectMember) else None

    async def get_workflow_template_version(
        self,
        version_id: UUID,
    ) -> WorkflowTemplateVersion | None:
        version = await self._session.get(WorkflowTemplateVersion, version_id)
        return version if isinstance(version, WorkflowTemplateVersion) else None

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]:
        conditions = [
            PhaseDocTemplate.phase_no == phase_no,
            PhaseDocTemplate.is_active.is_(True),
            or_(
                PhaseDocTemplate.requirement == PhaseDocRequirement.required,
                and_(
                    PhaseDocTemplate.requirement == PhaseDocRequirement.conditional,
                    PhaseDocTemplate.procurement_type == procurement_type,
                ),
            ),
        ]
        if procurement_type is None:
            conditions.append(PhaseDocTemplate.requirement == PhaseDocRequirement.required)

        result = await self._session.scalars(
            select(PhaseDocTemplate).where(*conditions).order_by(PhaseDocTemplate.doc_type),
        )
        return list(result.all())


class InMemoryDocumentClassificationRepository:
    def __init__(
        self,
        *,
        documents: list[Document] | None = None,
        main_projects: list[MainProject] | None = None,
        members: list[SubProjectMember] | None = None,
        phase_doc_templates: list[PhaseDocTemplate] | None = None,
        phases: list[Phase] | None = None,
        sub_projects: list[SubProject] | None = None,
        workflow_versions: list[WorkflowTemplateVersion] | None = None,
    ) -> None:
        self.documents = list(documents or [])
        self.main_projects = list(main_projects or [])
        self.members = list(members or [])
        self.phase_doc_templates = list(phase_doc_templates or [])
        self.phases = list(phases or [])
        self.sub_projects = list(sub_projects or [])
        self.workflow_versions = list(workflow_versions or [])

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        return next((phase for phase in self.phases if phase.id == phase_id), None)

    async def get_document(self, document_id: UUID) -> Document | None:
        return next((document for document in self.documents if document.id == document_id), None)

    async def get_main_project(self, main_project_id: UUID) -> MainProject | None:
        return next(
            (
                main_project
                for main_project in self.main_projects
                if main_project.id == main_project_id
            ),
            None,
        )

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        return next(
            (
                member
                for member in self.members
                if member.sub_project_id == sub_project_id and member.user_id == user_id
            ),
            None,
        )

    async def get_workflow_template_version(
        self,
        version_id: UUID,
    ) -> WorkflowTemplateVersion | None:
        return next(
            (version for version in self.workflow_versions if version.id == version_id),
            None,
        )

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]:
        templates = [
            template
            for template in self.phase_doc_templates
            if template.phase_no == phase_no
            and template.is_active
            and (
                template.requirement == PhaseDocRequirement.required
                or (
                    procurement_type is not None
                    and template.requirement == PhaseDocRequirement.conditional
                    and template.procurement_type == procurement_type
                )
            )
        ]
        return sorted(templates, key=lambda template: template.doc_type)


class DocumentClassificationService:
    def __init__(
        self,
        *,
        ai_service: AiProviderService | None = None,
        repository: DocumentClassificationRepository,
    ) -> None:
        self._ai_service = ai_service
        self._repository = repository

    async def suggest_document_type(
        self,
        *,
        actor: User,
        request: DocumentClassificationRequest,
        audit_context: AuditContext | None = None,
        audit_writer: AuditLogWriter | None = None,
    ) -> DocumentClassificationResult:
        resolved = await self._resolve_context(actor=actor, request=request)
        rule_suggestions = self._rule_suggestions(resolved)
        suggestions = await self._ai_suggestions(
            actor=actor,
            resolved=resolved,
            rule_suggestions=rule_suggestions,
        )
        result = DocumentClassificationResult(
            current_doc_type=resolved.current_doc_type,
            document_id=resolved.document_id,
            file_name=resolved.file_name,
            phase_id=resolved.phase.id,
            sub_project_id=resolved.sub_project.id,
            suggestions=suggestions,
        )
        self._record_suggestion(
            actor=actor,
            audit_context=audit_context,
            audit_writer=audit_writer,
            result=result,
        )
        return result

    async def _resolve_context(
        self,
        *,
        actor: User,
        request: DocumentClassificationRequest,
    ) -> _ResolvedClassificationContext:
        file_name = request.file_name.strip()
        if not file_name:
            raise ValidationFailedError("File name is required")

        sub_project = await self._repository.get_sub_project(request.sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        phase = await self._repository.get_phase(request.phase_id)
        if phase is None or phase.sub_project_id != sub_project.id:
            raise ResourceNotFoundError("Phase does not exist")
        await self._ensure_visible(actor, sub_project)

        current_doc_type = request.current_doc_type.strip() if request.current_doc_type else None
        document_id = request.document_id
        if document_id is not None:
            document = await self._repository.get_document(document_id)
            if document is None:
                raise ResourceNotFoundError("Document does not exist")
            if document.sub_project_id != sub_project.id or document.phase_id != phase.id:
                raise ValidationFailedError("Document is outside the requested phase")
            file_name = document.file_name
            current_doc_type = current_doc_type or document.doc_type

        main_project = await self._repository.get_main_project(sub_project.main_project_id)
        project_type_id = main_project.project_type_id if main_project is not None else None
        required_doc_types = await self._required_doc_types(sub_project=sub_project, phase=phase)
        return _ResolvedClassificationContext(
            current_doc_type=current_doc_type,
            document_id=document_id,
            file_name=file_name,
            phase=phase,
            project_type_id=project_type_id,
            required_doc_types=tuple(required_doc_types),
            sub_project=sub_project,
            summary=request.summary.strip() if request.summary else None,
        )

    async def _required_doc_types(self, *, sub_project: SubProject, phase: Phase) -> list[str]:
        if sub_project.workflow_template_version_id is not None:
            version = await self._repository.get_workflow_template_version(
                sub_project.workflow_template_version_id,
            )
            if version is not None:
                return _required_doc_types_from_workflow_version(version=version, phase=phase)

        templates = await self._repository.list_required_doc_templates(
            phase_no=phase.phase_no,
            procurement_type=phase.procurement_type,
        )
        return [template.doc_type for template in templates]

    async def _ensure_visible(self, actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_CLASSIFICATION_ROLES or sub_project.manager_id == actor.id:
            return
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=actor.id,
        )
        if member is not None:
            return
        raise PermissionDeniedError()

    def _rule_suggestions(
        self,
        resolved: _ResolvedClassificationContext,
    ) -> list[DocumentTypeSuggestion]:
        builder = _CandidateBuilder(required_doc_types=resolved.required_doc_types)

        if len(resolved.required_doc_types) == 1:
            builder.add(
                resolved.required_doc_types[0],
                0.96,
                "项目模板当前环节只要求该文档类型",
            )
        elif resolved.required_doc_types:
            for doc_type in resolved.required_doc_types:
                builder.add(doc_type, 0.58, "来自当前环节必传文档清单")

        searchable_text = "\n".join(
            [
                resolved.file_name,
                resolved.summary or "",
                resolved.current_doc_type or "",
            ],
        ).casefold()
        for keyword, doc_type, confidence in KEYWORD_RULES:
            if keyword.casefold() in searchable_text:
                builder.add(doc_type, confidence, f"文件名或摘要包含「{keyword}」")

        extension = Path(resolved.file_name).suffix.lower()
        if extension in EXTENSION_RULES:
            doc_type, confidence = EXTENSION_RULES[extension]
            builder.add(doc_type, confidence, f"文件扩展名为 {extension}")

        if resolved.current_doc_type:
            builder.add(resolved.current_doc_type, 0.55, "保留当前上传入口的文档类型")

        return builder.build()

    async def _ai_suggestions(
        self,
        *,
        actor: User,
        resolved: _ResolvedClassificationContext,
        rule_suggestions: list[DocumentTypeSuggestion],
    ) -> list[DocumentTypeSuggestion]:
        if self._ai_service is None or not rule_suggestions:
            return rule_suggestions

        prompt = _build_ai_prompt(resolved=resolved, rule_suggestions=rule_suggestions)
        try:
            payload = await self._ai_service.complete_json(
                actor_id=actor.id,
                prompt=prompt,
                purpose="document_classification",
                schema_name="document_type_suggestions",
            )
        except (AiProviderDisabledError, AiProviderError, AiSchemaValidationError):
            return rule_suggestions

        ai_items = cast(list[dict[str, object]], payload.get("suggestions", []))
        ai_suggestions = [
            DocumentTypeSuggestion(
                confidence=_clamp_confidence(item.get("confidence", 0.5)),
                doc_type=str(item.get("doc_type", "")).strip(),
                reason=str(item.get("reason", "")).strip() or "AI 基于规则候选重新排序",
                source="ai",
            )
            for item in ai_items
            if str(item.get("doc_type", "")).strip()
        ]
        if not ai_suggestions:
            return rule_suggestions
        return _merge_ai_and_rule_suggestions(ai_suggestions, rule_suggestions)

    @staticmethod
    def _record_suggestion(
        *,
        actor: User,
        audit_context: AuditContext | None,
        audit_writer: AuditLogWriter | None,
        result: DocumentClassificationResult,
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id,
                action="document_classification.suggest",
                target_type="document_classification",
                target_id=str(result.document_id or result.phase_id),
                before_state={},
                after_state={
                    "suggestions": [item.to_dict() for item in result.suggestions],
                },
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={
                    "current_doc_type": result.current_doc_type or "",
                    "file_name": result.file_name,
                    "phase_id": str(result.phase_id),
                    "sub_project_id": str(result.sub_project_id),
                },
                request_id=context.request_id,
            ),
        )


@dataclass(frozen=True)
class _ResolvedClassificationContext:
    sub_project: SubProject
    phase: Phase
    file_name: str
    current_doc_type: str | None
    document_id: UUID | None
    project_type_id: UUID | None
    required_doc_types: tuple[str, ...]
    summary: str | None


class _CandidateBuilder:
    def __init__(self, *, required_doc_types: tuple[str, ...]) -> None:
        self._items: dict[str, tuple[float, list[str]]] = {}
        self._required_doc_types = frozenset(required_doc_types)

    def add(self, doc_type: str, confidence: float, reason: str) -> None:
        cleaned_doc_type = doc_type.strip()
        if not cleaned_doc_type:
            return
        adjusted_confidence = (
            min(confidence + 0.05, 0.99)
            if cleaned_doc_type in self._required_doc_types
            else confidence
        )
        previous = self._items.get(cleaned_doc_type)
        if previous is None:
            self._items[cleaned_doc_type] = (adjusted_confidence, [reason])
            return

        previous_confidence, reasons = previous
        reasons.append(reason)
        self._items[cleaned_doc_type] = (max(previous_confidence, adjusted_confidence), reasons)

    def build(self) -> list[DocumentTypeSuggestion]:
        suggestions = [
            DocumentTypeSuggestion(
                confidence=round(_clamp_confidence(confidence), 2),
                doc_type=doc_type,
                reason="；".join(dict.fromkeys(reasons)),
                source="rules",
            )
            for doc_type, (confidence, reasons) in self._items.items()
        ]
        return sorted(suggestions, key=lambda item: (-item.confidence, item.doc_type))[:5]


def _required_doc_types_from_workflow_version(
    *,
    version: WorkflowTemplateVersion,
    phase: Phase,
) -> list[str]:
    definitions = [
        definition
        for definition in version.phase_definitions
        if _phase_definition_matches(definition, phase)
    ]
    if not definitions:
        return []

    doc_types: list[str] = []
    required_documents = cast(list[object], definitions[0].get("required_documents", []))
    for raw_document in required_documents:
        if not isinstance(raw_document, dict):
            continue
        document = cast(dict[str, object], raw_document)
        try:
            requirement = PhaseDocRequirement(str(document.get("requirement", "")))
        except ValueError:
            continue
        if requirement == PhaseDocRequirement.optional:
            continue

        procurement_type_value = document.get("procurement_type")
        if (
            requirement == PhaseDocRequirement.conditional
            and procurement_type_value is not None
            and phase.procurement_type != ProcurementType(str(procurement_type_value))
        ):
            continue
        doc_type = str(document.get("doc_type", "")).strip()
        if doc_type:
            doc_types.append(doc_type)
    return sorted(dict.fromkeys(doc_types))


def _phase_definition_matches(definition: dict[str, object], phase: Phase) -> bool:
    raw_order = definition.get("order")
    try:
        order = int(cast(str | int, raw_order))
    except (TypeError, ValueError):
        order = -1
    return order == phase.phase_no or definition.get("key") == phase.code


def _build_ai_prompt(
    *,
    resolved: _ResolvedClassificationContext,
    rule_suggestions: list[DocumentTypeSuggestion],
) -> str:
    rule_payload = [item.to_dict() for item in rule_suggestions]
    return (
        "You are classifying enterprise project documents. "
        "Return JSON with a suggestions array. Only use doc_type values from the "
        "rule candidates unless the filename clearly indicates a better internal code.\n"
        f"file_name: {resolved.file_name}\n"
        f"extension: {Path(resolved.file_name).suffix.lower()}\n"
        f"phase_no: {resolved.phase.phase_no}\n"
        f"phase_code: {resolved.phase.code}\n"
        f"project_type_id: {resolved.project_type_id}\n"
        f"current_doc_type: {resolved.current_doc_type}\n"
        f"summary: {resolved.summary or ''}\n"
        f"required_doc_types: {list(resolved.required_doc_types)}\n"
        f"rule_candidates: {rule_payload}\n"
        "Schema: {\"suggestions\":[{\"doc_type\":\"contract\","
        "\"confidence\":0.0,\"reason\":\"short reason\"}]}"
    )


def _merge_ai_and_rule_suggestions(
    ai_suggestions: list[DocumentTypeSuggestion],
    rule_suggestions: list[DocumentTypeSuggestion],
) -> list[DocumentTypeSuggestion]:
    merged: dict[str, DocumentTypeSuggestion] = {}
    for suggestion in ai_suggestions:
        merged[suggestion.doc_type] = suggestion
    for suggestion in rule_suggestions:
        merged.setdefault(suggestion.doc_type, suggestion)
    return list(merged.values())[:5]


def _clamp_confidence(value: object) -> float:
    if not isinstance(value, (int, float, str)):
        return 0.5
    try:
        numeric = float(value)
    except ValueError:
        return 0.5
    return max(0.0, min(1.0, numeric))
