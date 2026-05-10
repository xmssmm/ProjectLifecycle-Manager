from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.dingtalk_channel import (
    DingTalkHttpResponse,
    DingTalkNotificationChannel,
)
from app.services.notification_channels import (
    NotificationChannelMessage,
    NotificationChannelType,
)


class RecordingDingTalkTransport:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "ok",
        exc: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.exc = exc
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def post_json(self, url: str, payload: dict[str, object]) -> DingTalkHttpResponse:
        if self.exc is not None:
            raise self.exc
        self.calls.append((url, payload))
        return DingTalkHttpResponse(status_code=self.status_code, text=self.text)


def make_settings(secret: str = "top-secret") -> Settings:
    return Settings(
        dingtalk_enabled=True,
        dingtalk_webhook_url="https://oapi.dingtalk.com/robot/send?access_token=robot-token",
        dingtalk_webhook_secret=secret,
    )


@pytest.mark.asyncio
async def test_dingtalk_channel_appends_timestamp_and_signature() -> None:
    transport = RecordingDingTalkTransport()
    channel = DingTalkNotificationChannel(
        settings=make_settings(),
        transport=transport,
        timestamp_provider=lambda: 1_700_000_000_123,
    )

    await channel.send(make_message())

    url, _payload = transport.calls[0]
    query = parse_qs(urlparse(url).query)
    expected_sign = base64.b64encode(
        hmac.new(
            b"top-secret",
            b"1700000000123\ntop-secret",
            hashlib.sha256,
        ).digest(),
    ).decode("utf-8")
    assert query["access_token"] == ["robot-token"]
    assert query["timestamp"] == ["1700000000123"]
    assert query["sign"] == [expected_sign]


@pytest.mark.asyncio
async def test_dingtalk_channel_sends_markdown_with_business_link() -> None:
    transport = RecordingDingTalkTransport()
    channel = DingTalkNotificationChannel(
        settings=make_settings(secret=""),
        transport=transport,
    )

    result = await channel.send(
        make_message(
            scenario="project_pending_review",
            payload={
                "project_no": "P-001",
                "project_name": "数字化平台",
                "url": "https://pm.example.local/main-projects/project-1/review",
            },
        ),
    )

    assert result.success is True
    _url, payload = transport.calls[0]
    assert payload["msgtype"] == "markdown"
    markdown = payload["markdown"]
    assert isinstance(markdown, dict)
    assert markdown["title"] == "项目待审核"
    text = str(markdown["text"])
    assert "P-001" in text
    assert "数字化平台" in text
    assert "https://pm.example.local/main-projects/project-1/review" in text


@pytest.mark.asyncio
async def test_dingtalk_channel_returns_failure_for_timeout() -> None:
    channel = DingTalkNotificationChannel(
        settings=make_settings(secret=""),
        transport=RecordingDingTalkTransport(exc=TimeoutError("request timed out")),
    )

    result = await channel.send(make_message())

    assert result.success is False
    assert result.error == "DingTalk webhook request timed out"


@pytest.mark.asyncio
async def test_dingtalk_channel_returns_failure_for_non_2xx_response() -> None:
    transport = RecordingDingTalkTransport(status_code=500, text="server error")
    channel = DingTalkNotificationChannel(settings=make_settings(secret=""), transport=transport)

    result = await channel.send(make_message())

    assert result.success is False
    assert result.error == "DingTalk webhook returned 500: server error"


def make_message(
    *,
    scenario: str = "task_due_today",
    payload: dict[str, object] | None = None,
) -> NotificationChannelMessage:
    return NotificationChannelMessage(
        channel=NotificationChannelType.dingtalk,
        receiver_id=uuid4(),
        scenario=scenario,
        source_id="source-1",
        payload=payload
        or {
            "task_no": "T-001",
            "title": "提交验收材料",
            "due_date": "2026-05-10",
            "url": "https://pm.example.local/tasks/task-1",
        },
        dedup_key="task_due_today:user:source-1:20260510",
    )
