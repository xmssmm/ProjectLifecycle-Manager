from fastapi import APIRouter

from app.api.external.v1.documents import router as documents_router
from app.api.external.v1.payments import router as payments_router
from app.api.external.v1.projects import router as projects_router

router = APIRouter(prefix="/api/external/v1")
router.include_router(projects_router)
router.include_router(payments_router)
router.include_router(documents_router)
