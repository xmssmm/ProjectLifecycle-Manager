from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from app.core.config import Settings
from app.storage.base import StorageSecurityError
from app.storage.factory import create_storage_backend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend

FIXED_UUID = UUID("12345678-1234-5678-1234-567812345678")


def fixed_uuid() -> UUID:
    return FIXED_UUID


def test_local_storage_saves_file_under_sub_phase_uuid_path(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root=tmp_path, uuid_factory=fixed_uuid)

    storage_key = storage.save(
        sub_id="sub-001",
        phase_id="phase-002",
        filename="Acceptance.PDF",
        content=b"contract-bytes",
    )

    assert storage_key == "sub-001/phase-002/12345678-1234-5678-1234-567812345678.pdf"
    assert (tmp_path / storage_key).read_bytes() == b"contract-bytes"


def test_local_storage_reads_deletes_and_builds_url(tmp_path: Path) -> None:
    storage = LocalStorageBackend(
        root=tmp_path, public_url_prefix="/files", uuid_factory=fixed_uuid
    )
    storage_key = storage.save(
        sub_id="sub-001",
        phase_id="phase-002",
        filename="minutes.txt",
        content=b"meeting-minutes",
    )

    assert storage.read(storage_key) == b"meeting-minutes"
    assert (
        storage.get_url(storage_key)
        == "/files/sub-001/phase-002/12345678-1234-5678-1234-567812345678.txt"
    )

    storage.delete(storage_key)

    assert not (tmp_path / storage_key).exists()


@pytest.mark.parametrize(
    ("kwargs", "method"),
    [
        ({"sub_id": "../sub", "phase_id": "phase-002", "filename": "safe.pdf"}, "save"),
        ({"sub_id": "sub-001", "phase_id": "..\\phase", "filename": "safe.pdf"}, "save"),
        ({"sub_id": "sub-001", "phase_id": "phase-002", "filename": "../evil.pdf"}, "save"),
        ({"storage_key": "../evil.pdf"}, "read"),
        ({"storage_key": "sub-001/../../evil.pdf"}, "delete"),
        ({"storage_key": "sub-001/phase-002/.."}, "get_url"),
    ],
)
def test_local_storage_rejects_path_traversal(
    tmp_path: Path,
    kwargs: dict[str, str],
    method: str,
) -> None:
    storage = LocalStorageBackend(root=tmp_path, uuid_factory=fixed_uuid)

    with pytest.raises(StorageSecurityError):
        if method == "save":
            storage.save(content=b"payload", **kwargs)
        elif method == "read":
            storage.read(**kwargs)
        elif method == "delete":
            storage.delete(**kwargs)
        else:
            storage.get_url(**kwargs)


def test_storage_factory_switches_backend_from_settings(tmp_path: Path) -> None:
    local_backend = create_storage_backend(
        Settings(storage_backend="local", storage_root=str(tmp_path))
    )
    s3_backend = create_storage_backend(Settings(storage_backend="s3", s3_bucket="archive-bucket"))

    assert isinstance(local_backend, LocalStorageBackend)
    assert isinstance(s3_backend, S3StorageBackend)
