from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Protocol
from zipfile import BadZipFile, ZipFile

from app.core.exceptions import ValidationFailedError

ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".jpg",
        ".jpeg",
        ".png",
        ".zip",
    },
)

BLOCKED_EXTENSIONS = frozenset(
    {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".pif",
        ".ps1",
        ".psm1",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".wsf",
        ".wsh",
        ".msi",
        ".msp",
        ".dll",
        ".sh",
        ".bash",
        ".zsh",
        ".jar",
        ".app",
    },
)

MIME_TYPES_BY_EXTENSION: Mapping[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".doc": frozenset({"application/msword"}),
    ".docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ),
    ".xls": frozenset({"application/vnd.ms-excel"}),
    ".xlsx": frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ),
    ".ppt": frozenset({"application/vnd.ms-powerpoint"}),
    ".pptx": frozenset(
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".png": frozenset({"image/png"}),
    ".zip": frozenset({"application/zip", "application/x-zip-compressed"}),
}

OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
MAGIC_SIGNATURES_BY_EXTENSION: Mapping[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".doc": (OLE_SIGNATURE,),
    ".docx": ZIP_SIGNATURES,
    ".xls": (OLE_SIGNATURE,),
    ".xlsx": ZIP_SIGNATURES,
    ".ppt": (OLE_SIGNATURE,),
    ".pptx": ZIP_SIGNATURES,
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".zip": ZIP_SIGNATURES,
}
ZIP_SCANNED_EXTENSIONS = frozenset({".zip", ".docx", ".xlsx", ".pptx"})
MAX_ZIP_SCAN_DEPTH = 3


class FileValidationError(ValidationFailedError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("File validation failed", data={"rejection_reason": reason})


class FileValidator(Protocol):
    def validate(self, *, filename: str, content_type: str | None, content: bytes) -> None:
        ...


class DefaultFileValidator:
    def validate(self, *, filename: str, content_type: str | None, content: bytes) -> None:
        extension = self._extension(filename)
        if extension not in ALLOWED_EXTENSIONS:
            raise FileValidationError("extension_not_allowed")
        if extension in BLOCKED_EXTENSIONS:
            raise FileValidationError("extension_blocked")

        normalized_mime = self._normalize_mime(content_type)
        if normalized_mime not in MIME_TYPES_BY_EXTENSION[extension]:
            raise FileValidationError("mime_not_allowed")

        signatures = MAGIC_SIGNATURES_BY_EXTENSION[extension]
        if not any(content.startswith(signature) for signature in signatures):
            raise FileValidationError("magic_mismatch")

        if extension in ZIP_SCANNED_EXTENSIONS:
            self._scan_zip_content(content, depth=0)

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower()

    @staticmethod
    def _normalize_mime(content_type: str | None) -> str:
        return (content_type or "").split(";", maxsplit=1)[0].strip().lower()

    def _scan_zip_content(self, content: bytes, *, depth: int) -> None:
        if depth > MAX_ZIP_SCAN_DEPTH:
            raise FileValidationError("zip_nested_too_deep")

        try:
            with ZipFile(BytesIO(content)) as archive:
                for info in archive.infolist():
                    self._scan_zip_member_name(info.filename)
                    if Path(info.filename).suffix.lower() == ".zip":
                        self._scan_zip_content(archive.read(info), depth=depth + 1)
        except BadZipFile as exc:
            raise FileValidationError("zip_invalid") from exc

    @staticmethod
    def _scan_zip_member_name(filename: str) -> None:
        normalized = filename.replace("\\", "/")
        for part in PurePosixPath(normalized).parts:
            if Path(part).suffix.lower() in BLOCKED_EXTENSIONS:
                raise FileValidationError("zip_contains_blocked_extension")
