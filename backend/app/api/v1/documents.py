from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal, get_db_session
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.documents import Document
from app.models.users import User
from app.schemas.documents import DocumentListRead, DocumentRead
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.documents import (
    DocumentService,
    LibreOfficeDocumentConverter,
    SqlAlchemyDocumentRepository,
)
from app.storage.factory import create_storage_backend
from app.tasks.document_scanning import CeleryDocumentScanScheduler
from app.tasks.search import CeleryDocumentSearchScheduler

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentService:
    return DocumentService(
        repository=SqlAlchemyDocumentRepository(session),
        storage=create_storage_backend(settings),
        max_file_size_bytes=settings.max_upload_size_bytes,
        office_converter=LibreOfficeDocumentConverter(
            binary_path=settings.office_preview_converter_binary,
            timeout_seconds=settings.office_preview_conversion_timeout_seconds,
        ),
        scan_scheduler=CeleryDocumentScanScheduler(),
        search_scheduler=CeleryDocumentSearchScheduler(),
    )


def serialize_document(document: Document) -> dict[str, object]:
    return DocumentRead.model_validate(document).model_dump(mode="json")


def serialize_uploaded_document(document: Document) -> dict[str, object]:
    payload = serialize_document(document)
    payload["doc_id"] = payload["id"]
    return payload


def office_preview_pdf_filename(file_name: str) -> str:
    base_name = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    return f"{base_name}.pdf"


@router.post("")
async def upload_document(
    background_tasks: BackgroundTasks,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[User, Depends(require_permission("document.upload"))],
    file: Annotated[UploadFile, File()],
    sub_project_id: Annotated[UUID, Form()],
    phase_id: Annotated[UUID, Form()],
    doc_type: Annotated[str, Form()],
    acceptance_step_id: Annotated[UUID | None, Form()] = None,
) -> dict[str, object]:
    content = await file.read()
    document = await service.upload_document(
        actor=current_user,
        sub_project_id=sub_project_id,
        phase_id=phase_id,
        doc_type=doc_type,
        file_name=file.filename or "",
        content_type=file.content_type,
        content=content,
        acceptance_step_id=acceptance_step_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_uploaded_document(document))


@router.get("")
async def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[User, Depends(require_permission("document.download"))],
    sub_project_id: Annotated[UUID, Query()],
    phase_id: Annotated[UUID | None, Query()] = None,
    doc_type: Annotated[str | None, Query()] = None,
    include_history: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    documents = await service.list_documents(
        actor=current_user,
        sub_project_id=sub_project_id,
        phase_id=phase_id,
        doc_type=doc_type,
        include_history=include_history,
    )
    payload = DocumentListRead(
        items=[DocumentRead.model_validate(document) for document in documents],
        total=len(documents),
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[User, Depends(require_permission("document.download"))],
) -> StreamingResponse:
    download = await service.download_document(actor=current_user, document_id=document_id)
    encoded_filename = quote(download.document.file_name)
    return StreamingResponse(
        iter([download.content]),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[User, Depends(require_permission("document.download"))],
) -> StreamingResponse:
    preview = await service.preview_document(
        actor=current_user,
        document_id=document_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    encoded_filename = quote(preview.document.file_name)
    return StreamingResponse(
        iter([preview.content]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/{document_id}/preview-office")
async def preview_office_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[User, Depends(require_permission("document.download"))],
) -> StreamingResponse:
    preview = await service.preview_office_document(
        actor=current_user,
        document_id=document_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    encoded_filename = quote(office_preview_pdf_filename(preview.document.file_name))
    return StreamingResponse(
        iter([preview.content]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
        },
    )
