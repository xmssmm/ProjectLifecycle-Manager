from __future__ import annotations

from pathlib import Path


class DocumentTextExtractionError(ValueError):
    pass


class DocumentTextExtractor:
    def extract_text(self, *, file_name: str, content: bytes) -> str:
        suffix = Path(file_name).suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf_text(content)
        return self._decode_text(content)

    @staticmethod
    def _decode_text(content: bytes) -> str:
        for encoding in ("utf-8", "utf-16", "gb18030"):
            try:
                return content.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def _extract_pdf_text(content: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency exists in runtime image
            raise DocumentTextExtractionError("PDF text extractor is unavailable") from exc

        try:
            from io import BytesIO

            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:  # noqa: BLE001
            raise DocumentTextExtractionError(str(exc)) from exc
