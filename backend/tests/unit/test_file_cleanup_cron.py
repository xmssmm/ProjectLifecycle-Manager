from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module
from types import ModuleType
from uuid import uuid4

import pytest

from app.models.documents import Document


def load_cleanup_module() -> ModuleType:
    try:
        return import_module("app.services.file_cleanup")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.services.file_cleanup is required: {exc}")


def make_document(
    *,
    file_path: str,
    is_deleted: bool,
    updated_at: datetime,
) -> Document:
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=uuid4(),
        phase_id=uuid4(),
        acceptance_step_id=None,
        doc_type="meeting_material",
        file_name=file_path.rsplit("/", maxsplit=1)[-1],
        file_path=file_path,
        file_size=128,
        version=1,
        is_latest=True,
        is_deleted=is_deleted,
        uploader_id=uuid4(),
        created_at=updated_at,
        updated_at=updated_at,
    )


class RecordingCleanupLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


@pytest.mark.asyncio
async def test_file_cleanup_dry_run_reports_candidates_without_deleting() -> None:
    cleanup_module = load_cleanup_module()
    now = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    old = now - timedelta(days=8)
    deleted_at = now - timedelta(days=91)
    logger = RecordingCleanupLogger()
    storage = cleanup_module.InMemoryStorageCleanupBackend(
        files=[
            cleanup_module.StorageFile(storage_key="tmp/orphan-old.tmp", modified_at=old),
            cleanup_module.StorageFile(storage_key="docs/active.pdf", modified_at=old),
            cleanup_module.StorageFile(storage_key="docs/deleted-old.pdf", modified_at=old),
        ],
    )
    repository = cleanup_module.InMemoryFileCleanupRepository(
        documents=[
            make_document(
                file_path="docs/active.pdf",
                is_deleted=False,
                updated_at=now,
            ),
            make_document(
                file_path="docs/deleted-old.pdf",
                is_deleted=True,
                updated_at=deleted_at,
            ),
        ],
    )
    service = cleanup_module.FileCleanupService(
        repository=repository,
        storage=storage,
        now_provider=lambda: now,
        logger=logger,
    )

    result = await service.cleanup(dry_run=True)

    assert result.dry_run is True
    assert result.orphan_files == ["tmp/orphan-old.tmp"]
    assert result.soft_deleted_files == ["docs/deleted-old.pdf"]
    assert result.deleted_files == []
    assert storage.deleted_keys == []
    assert logger.events[-1] == (
        "file_cleanup.completed",
        {
            "dry_run": True,
            "scanned_files": 3,
            "orphan_files": 1,
            "soft_deleted_files": 1,
            "deleted_files": 0,
        },
    )


@pytest.mark.asyncio
async def test_file_cleanup_deletes_only_stale_orphans_and_old_soft_deleted_files() -> None:
    cleanup_module = load_cleanup_module()
    now = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    old = now - timedelta(days=8)
    recent = now - timedelta(days=6, hours=23)
    deleted_old = now - timedelta(days=90, minutes=1)
    deleted_recent = now - timedelta(days=89)
    storage = cleanup_module.InMemoryStorageCleanupBackend(
        files=[
            cleanup_module.StorageFile(storage_key="tmp/orphan-old.tmp", modified_at=old),
            cleanup_module.StorageFile(storage_key="tmp/orphan-recent.tmp", modified_at=recent),
            cleanup_module.StorageFile(storage_key="docs/active.pdf", modified_at=old),
            cleanup_module.StorageFile(storage_key="docs/deleted-old.pdf", modified_at=old),
            cleanup_module.StorageFile(storage_key="docs/deleted-recent.pdf", modified_at=old),
        ],
    )
    repository = cleanup_module.InMemoryFileCleanupRepository(
        documents=[
            make_document(
                file_path="docs/active.pdf",
                is_deleted=False,
                updated_at=now,
            ),
            make_document(
                file_path="docs/deleted-old.pdf",
                is_deleted=True,
                updated_at=deleted_old,
            ),
            make_document(
                file_path="docs/deleted-recent.pdf",
                is_deleted=True,
                updated_at=deleted_recent,
            ),
        ],
    )
    service = cleanup_module.FileCleanupService(
        repository=repository,
        storage=storage,
        now_provider=lambda: now,
    )

    result = await service.cleanup(dry_run=False)

    assert result.orphan_files == ["tmp/orphan-old.tmp"]
    assert result.soft_deleted_files == ["docs/deleted-old.pdf"]
    assert result.deleted_files == ["docs/deleted-old.pdf", "tmp/orphan-old.tmp"]
    assert storage.deleted_keys == ["docs/deleted-old.pdf", "tmp/orphan-old.tmp"]
    assert storage.remaining_keys == [
        "docs/active.pdf",
        "docs/deleted-recent.pdf",
        "tmp/orphan-recent.tmp",
    ]


def test_celery_beat_schedules_file_cleanup_monday_0300() -> None:
    from app.tasks.celery_app import create_celery_app
    from app.tasks.task_names import FILE_CLEANUP_TASK_NAME

    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["file-cleanup-weekly-monday-0300"]
    assert schedule["task"] == FILE_CLEANUP_TASK_NAME
    assert "0 3 * *" in str(schedule["schedule"])
    assert "monday" in str(schedule["schedule"]).lower()
