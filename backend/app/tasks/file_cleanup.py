from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.file_cleanup import (
    FileCleanupService,
    LocalStorageCleanupBackend,
    SqlAlchemyFileCleanupRepository,
)
from app.tasks.celery_app import celery_app
from app.tasks.task_names import FILE_CLEANUP_TASK_NAME


async def run_file_cleanup(*, dry_run: bool = False) -> dict[str, object]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = FileCleanupService(
            repository=SqlAlchemyFileCleanupRepository(session),
            storage=LocalStorageCleanupBackend(root=settings.storage_root),
        )
        result = await service.cleanup(dry_run=dry_run)
        return result.to_dict()


@celery_app.task(name=FILE_CLEANUP_TASK_NAME)  # type: ignore[untyped-decorator]
def cleanup_storage_files(dry_run: bool = False) -> dict[str, object]:
    return asyncio.run(run_file_cleanup(dry_run=dry_run))
