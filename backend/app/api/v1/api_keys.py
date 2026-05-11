from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.api_keys import ApiKey
from app.models.users import User, UserRole
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreateRead, ApiKeyListRead, ApiKeyRead
from app.services.api_keys import (
    ApiKeyCreateResult,
    ApiKeyService,
    SqlAlchemyApiKeyRepository,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


async def get_api_key_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiKeyService:
    return ApiKeyService(repository=SqlAlchemyApiKeyRepository(session))


def serialize_api_key(api_key: ApiKey) -> dict[str, object]:
    return ApiKeyRead.model_validate(api_key).model_dump(mode="json")


def serialize_create_result(result: ApiKeyCreateResult) -> dict[str, object]:
    payload = ApiKeyCreateRead(
        api_key=ApiKeyRead.model_validate(result.api_key),
        token=result.token,
    )
    return payload.model_dump(mode="json")


@router.get("")
async def list_api_keys(
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    api_keys, total = await service.list_keys(actor=current_user, page=page, page_size=page_size)
    payload = ApiKeyListRead(
        items=[ApiKeyRead.model_validate(api_key) for api_key in api_keys],
        total=total,
        page=page,
        page_size=page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def create_api_key(
    payload: ApiKeyCreate,
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    result = await service.create_key(actor=current_user, payload=payload)
    return success_response(serialize_create_result(result))


@router.delete("/{api_key_id}")
async def revoke_api_key(
    api_key_id: UUID,
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    api_key = await service.revoke_key(actor=current_user, api_key_id=api_key_id)
    return success_response(serialize_api_key(api_key))
