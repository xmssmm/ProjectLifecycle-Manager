from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.ai_audit import AiAuditLogger, InMemoryAiAuditLogRepository
from app.services.ai_providers import AiProviderService, FakeAiProvider


@pytest.mark.asyncio
async def test_ai_audit_redacts_secrets_and_avoids_full_payload_storage() -> None:
    audit_repository = InMemoryAiAuditLogRepository()
    service = AiProviderService(
        audit_logger=AiAuditLogger(audit_repository),
        provider=FakeAiProvider(
            {"risk_summary": {"summary": "风险可控", "recommendations": ["继续监控"]}},
        ),
        settings=Settings(
            ai_api_key="sk-test-secret",
            ai_enabled=True,
            ai_model="fake-risk",
            ai_provider="fake",
        ),
    )
    sensitive_prompt = (
        "请总结项目风险。API key sk-test-secret。"
        "完整敏感 payload: customer=Alice, id_card=110101199001011234, budget=100。"
    )

    await service.complete_json(
        actor_id=uuid4(),
        prompt=sensitive_prompt,
        purpose="risk_summary",
        schema_name="risk_summary",
    )

    entry = audit_repository.entries[-1]
    audit_payload = entry.to_dict()
    assert "sk-test-secret" not in str(audit_payload)
    assert "110101199001011234" not in str(audit_payload)
    assert sensitive_prompt not in str(audit_payload)
    assert audit_payload["provider"] == "fake"
    assert isinstance(audit_payload["token_estimate"], int)
    assert audit_payload["token_estimate"] > 0
