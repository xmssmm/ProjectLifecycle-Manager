from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.notification_channels import (
    NotificationChannelMessage,
    NotificationChannelType,
)
from app.services.wework_channel import (
    WeworkHttpResponse,
    WeworkNotificationChannel,
)


class RecordingWeworkTransport:
    def __init__(self, *, status_code: int = 200, text: str = "ok") -> None:
        self.status_code = status_code
        self.text = text
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def post_json(self, url: str, payload: dict[str, object]) -> WeworkHttpResponse:
        self.calls.append((url, payload))
        return WeworkHttpResponse(status_code=self.status_code, text=self.text)


def make_settings(secret: str = "top-secret") -> Settings:
    return Settings(
        wework_enabled=True,
        wework_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=robot-key",
        wework_webhook_secret=secret,
    )


@pytest.mark.asyncio
async def test_wework_channel_appends_timestamp_and_signature() -> None:
    transport = RecordingWeworkTransport()
    channel = WeworkNotificationChannel(
        settings=make_settings(),
        transport=transport,
        timestamp_provider=lambda: 1_700_000_000,
    )

    await channel.send(make_message())

    url, _payload = transport.calls[0]
    query = parse_qs(urlparse(url).query)
    expected_sign = base64.b64encode(
        hmac.new(
            b"top-secret",
            b"1700000000\ntop-secret",
            hashlib.sha256,
        ).digest(),
    ).decode("utf-8")
    assert query["key"] == ["robot-key"]
    assert query["timestamp"] == ["1700000000"]
    assert query["sign"] == [expected_sign]


@pytest.mark.asyncio
async def test_wework_channel_sends_markdown_with_business_link() -> None:
    transport = RecordingWeworkTransport()
    channel = WeworkNotificationChannel(
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
    content = str(markdown["content"])
    assert "P-001" in content
    assert "数字化平台" in content
    assert "https://pm.example.local/main-projects/project-1/review" in content


@pytest.mark.asyncio
async def test_wework_channel_returns_failure_for_non_2xx_response() -> None:
    transport = RecordingWeworkTransport(status_code=500, text="server error")
    channel = WeworkNotificationChannel(settings=make_settings(secret=""), transport=transport)

    result = await channel.send(make_message())

    assert result.success is False
    assert result.error == "WeWork webhook returned 500: server error"


def make_message(
    *,
    scenario: str = "task_due_today",
    payload: dict[str, object] | None = None,
) -> NotificationChannelMessage:
    return NotificationChannelMessage(
        channel=NotificationChannelType.wework,
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
