from __future__ import annotations

from app.services.virus_scan import (
    EICAR_TEST_CONTENT,
    EicarSignatureVirusScanner,
    VirusScanStatus,
)


def test_eicar_signature_scanner_detects_eicar_content() -> None:
    scanner = EicarSignatureVirusScanner()

    result = scanner.scan_bytes(file_name="eicar.txt", content=EICAR_TEST_CONTENT)

    assert result.status == VirusScanStatus.infected
    assert "EICAR-Test-File" in result.result


def test_eicar_signature_scanner_marks_normal_content_clean() -> None:
    scanner = EicarSignatureVirusScanner()

    result = scanner.scan_bytes(file_name="contract.txt", content=b"normal document")

    assert result.status == VirusScanStatus.clean
    assert result.result == "No threats found"
