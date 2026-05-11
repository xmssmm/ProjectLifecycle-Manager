from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID

import httpx

from app.core.config import Settings
from app.schemas.ai import AiResponseValidationError, validate_ai_schema
from app.services.ai_audit import AiAuditLogger


class AiProviderDisabledError(RuntimeError):
    pass


class AiProviderError(RuntimeError):
    pass


class AiSchemaValidationError(ValueError):
    pass


class AiProvider(Protocol):
    async def complete_json(self, *, prompt: str, schema_name: str) -> Mapping[str, Any]: ...


class FakeAiProvider:
    def __init__(self, fixtures: Mapping[str, Mapping[str, Any]]) -> None:
        self._fixtures = fixtures

    async def complete_json(self, *, prompt: str, schema_name: str) -> Mapping[str, Any]:
        _ = prompt
        return dict(self._fixtures.get(schema_name, {}))


class OpenAICompatibleAiProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete_json(self, *, prompt: str, schema_name: str) -> Mapping[str, Any]:
        _ = schema_name
        url = f"{self._settings.ai_base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._settings.ai_api_key:
            headers["Authorization"] = f"Bearer {self._settings.ai_api_key}"
        payload = {
            "messages": [{"content": prompt, "role": "user"}],
            "model": self._settings.ai_model,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self._settings.ai_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise AiProviderError("AI provider returned non-object JSON")
        return parsed


class AiProviderService:
    def __init__(
        self,
        *,
        audit_logger: AiAuditLogger,
        provider: AiProvider | None = None,
        settings: Settings,
    ) -> None:
        self._audit_logger = audit_logger
        self._provider = provider or self._provider_from_settings(settings)
        self._settings = settings

    async def complete_json(
        self,
        *,
        actor_id: UUID | None,
        prompt: str,
        purpose: str,
        schema_name: str,
    ) -> dict[str, object]:
        if not self._settings.ai_enabled:
            raise AiProviderDisabledError("AI provider is disabled")

        try:
            raw_result = await self._provider.complete_json(prompt=prompt, schema_name=schema_name)
        except Exception as exc:
            await self._record(
                actor_id=actor_id,
                error_code="provider_error",
                error_message=str(exc),
                prompt=prompt,
                purpose=purpose,
                schema_name=schema_name,
                status="failed",
            )
            raise AiProviderError(str(exc)) from exc

        try:
            result = validate_ai_schema(schema_name, raw_result)
        except AiResponseValidationError as exc:
            await self._record(
                actor_id=actor_id,
                error_code="schema_validation_failed",
                error_message=str(exc),
                prompt=prompt,
                purpose=purpose,
                schema_name=schema_name,
                status="failed",
            )
            raise AiSchemaValidationError(str(exc)) from exc

        await self._record(
            actor_id=actor_id,
            prompt=prompt,
            purpose=purpose,
            schema_name=schema_name,
            status="succeeded",
        )
        return result

    async def _record(
        self,
        *,
        actor_id: UUID | None,
        prompt: str,
        purpose: str,
        schema_name: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await self._audit_logger.record(
            actor_id=actor_id,
            error_code=error_code,
            error_message=error_message,
            model=self._settings.ai_model or None,
            prompt=prompt,
            provider=self._settings.ai_provider,
            purpose=purpose,
            schema_name=schema_name,
            status=status,
        )

    @staticmethod
    def _provider_from_settings(settings: Settings) -> AiProvider:
        if settings.ai_provider == "fake":
            return FakeAiProvider({})
        return OpenAICompatibleAiProvider(settings)
