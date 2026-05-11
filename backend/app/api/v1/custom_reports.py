from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.users import User
from app.schemas.custom_reports import CustomReportDefinitionCreate, ReportQueryConfig
from app.services.audit import (
    AuditContext,
    AuditLogWriter,
    BackgroundAuditLogWriter,
    get_audit_context,
)
from app.services.custom_reports import (
    CustomReportService,
    SqlAlchemyCustomReportQueryExecutor,
    SqlAlchemyCustomReportRepository,
)

router = APIRouter(prefix="/custom-reports", tags=["custom-reports"])


async def get_custom_report_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CustomReportService:
    return CustomReportService(
        repository=SqlAlchemyCustomReportRepository(session),
        query_executor=SqlAlchemyCustomReportQueryExecutor(session),
    )


def get_custom_report_audit_writer(background_tasks: BackgroundTasks) -> AuditLogWriter:
    return BackgroundAuditLogWriter(
        background_tasks=background_tasks,
        session_factory=AsyncSessionLocal,
    )


@router.get("/datasets")
async def list_custom_report_datasets(
    service: Annotated[CustomReportService, Depends(get_custom_report_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    datasets = service.list_datasets(actor=current_user)
    return success_response([item.model_dump(mode="json") for item in datasets])


@router.post("/preview")
async def preview_custom_report_query(
    payload: ReportQueryConfig,
    service: Annotated[CustomReportService, Depends(get_custom_report_service)],
    audit_writer: Annotated[AuditLogWriter, Depends(get_custom_report_audit_writer)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    preview = await service.preview_query(
        actor=current_user,
        query_config=payload,
        audit_writer=audit_writer,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(preview.model_dump(mode="json"))


@router.post("")
async def create_custom_report(
    payload: CustomReportDefinitionCreate,
    service: Annotated[CustomReportService, Depends(get_custom_report_service)],
    audit_writer: Annotated[AuditLogWriter, Depends(get_custom_report_audit_writer)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    report = await service.create_report(
        actor=current_user,
        payload=payload,
        audit_writer=audit_writer,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(service.serialize_report(report))


@router.get("")
async def list_custom_reports(
    service: Annotated[CustomReportService, Depends(get_custom_report_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    reports = await service.list_reports(actor=current_user)
    return success_response([service.serialize_report(report) for report in reports])


@router.post("/{report_id}/preview")
async def preview_saved_custom_report(
    report_id: UUID,
    service: Annotated[CustomReportService, Depends(get_custom_report_service)],
    audit_writer: Annotated[AuditLogWriter, Depends(get_custom_report_audit_writer)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    preview = await service.preview_report(
        actor=current_user,
        report_id=report_id,
        audit_writer=audit_writer,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(preview.model_dump(mode="json"))


@router.delete("/{report_id}")
async def delete_custom_report(
    report_id: UUID,
    service: Annotated[CustomReportService, Depends(get_custom_report_service)],
    audit_writer: Annotated[AuditLogWriter, Depends(get_custom_report_audit_writer)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    report = await service.delete_report(
        actor=current_user,
        report_id=report_id,
        audit_writer=audit_writer,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(service.serialize_report(report))
