from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.ai_audit import AiAuditLogger, InMemoryAiAuditLogRepository
from app.services.ai_providers import (
    AiProviderDisabledError,
    AiProviderService,
    AiSchemaValidationError,
    FakeAiProvider,
)


@pytest.mark.asyncio
async def test_ai_provider_is_disabled_by_default() -> None:
    service = AiProviderService(
        audit_logger=AiAuditLogger(InMemoryAiAuditLogRepository()),
        provider=FakeAiProvider({"risk_summary": {"summary": "ok", "recommendations": []}}),
        settings=Settings(),
    )

    with pytest.raises(AiProviderDisabledError):
        await service.complete_json(
            actor_id=uuid4(),
            prompt="summarize risk",
            purpose="risk_summary",
            schema_name="risk_summary",
        )


@pytest.mark.asyncio
async def test_fake_ai_provider_returns_valid_schema_result() -> None:
    audit_repository = InMemoryAiAuditLogRepository()
    service = AiProviderService(
        audit_logger=AiAuditLogger(audit_repository),
        provider=FakeAiProvider(
            {"risk_summary": {"summary": "预算偏差较高", "recommendations": ["复核预算"]}},
        ),
        settings=Settings(ai_enabled=True, ai_provider="fake", ai_model="fake-risk"),
    )

    result = await service.complete_json(
        actor_id=uuid4(),
        prompt="summarize risk",
        purpose="risk_summary",
        schema_name="risk_summary",
    )

    assert result == {"summary": "预算偏差较高", "recommendations": ["复核预算"]}
    assert audit_repository.entries[-1].status == "succeeded"
    assert audit_repository.entries[-1].schema_name == "risk_summary"


@pytest.mark.asyncio
async def test_invalid_ai_schema_result_records_failed_audit() -> None:
    audit_repository = InMemoryAiAuditLogRepository()
    service = AiProviderService(
        audit_logger=AiAuditLogger(audit_repository),
        provider=FakeAiProvider({"risk_summary": {"recommendations": ["缺少摘要"]}}),
        settings=Settings(ai_enabled=True, ai_provider="fake", ai_model="fake-risk"),
    )

    with pytest.raises(AiSchemaValidationError):
        await service.complete_json(
            actor_id=uuid4(),
            prompt="summarize risk",
            purpose="risk_summary",
            schema_name="risk_summary",
        )

    assert audit_repository.entries[-1].status == "failed"
    assert audit_repository.entries[-1].error_code == "schema_validation_failed"
