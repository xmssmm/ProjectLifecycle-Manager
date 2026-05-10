from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.services.notification_channels import (
    ChannelDeliveryResult,
    NotificationChannelMessage,
    NotificationChannelType,
)


@dataclass(frozen=True)
class WeworkHttpResponse:
    status_code: int
    text: str


class WeworkHttpTransport(Protocol):
    async def post_json(self, url: str, payload: dict[str, object]) -> WeworkHttpResponse:
        ...


class UrllibWeworkHttpTransport:
    async def post_json(self, url: str, payload: dict[str, object]) -> WeworkHttpResponse:
        return await asyncio.to_thread(self._post_json_sync, url, payload)

    @staticmethod
    def _post_json_sync(url: str, payload: dict[str, object]) -> WeworkHttpResponse:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                text = response.read().decode("utf-8", errors="replace")
                return WeworkHttpResponse(status_code=response.status, text=text)
        except HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            return WeworkHttpResponse(status_code=exc.code, text=text)
        except URLError as exc:
            return WeworkHttpResponse(status_code=0, text=str(exc.reason))


class WeworkNotificationChannel:
    def __init__(
        self,
        *,
        settings: Settings,
        transport: WeworkHttpTransport | None = None,
        timestamp_provider: Callable[[], int] | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport or UrllibWeworkHttpTransport()
        self._timestamp_provider = timestamp_provider or (lambda: int(time.time()))

    async def send(self, message: NotificationChannelMessage) -> ChannelDeliveryResult:
        if not self._settings.wework_enabled:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.wework,
                success=False,
                error="WeWork channel is disabled",
            )
        if not self._settings.wework_webhook_url:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.wework,
                success=False,
                error="WeWork webhook URL is not configured",
            )

        response = await self._transport.post_json(
            self._webhook_url(),
            {"msgtype": "markdown", "markdown": {"content": self._render_markdown(message)}},
        )
        if 200 <= response.status_code < 300:
            return ChannelDeliveryResult(channel=NotificationChannelType.wework, success=True)
        return ChannelDeliveryResult(
            channel=NotificationChannelType.wework,
            success=False,
            error=f"WeWork webhook returned {response.status_code}: {response.text}",
        )

    def _webhook_url(self) -> str:
        url = self._settings.wework_webhook_url
        secret = self._settings.wework_webhook_secret
        if not secret:
            return url

        timestamp = str(self._timestamp_provider())
        sign = self._signature(timestamp=timestamp, secret=secret)
        parts = urlsplit(url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        query.extend([("timestamp", timestamp), ("sign", sign)])
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment),
        )

    @staticmethod
    def _signature(*, timestamp: str, secret: str) -> str:
        payload = f"{timestamp}\n{secret}".encode()
        digest = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _render_markdown(self, message: NotificationChannelMessage) -> str:
        payload = message.payload
        url = str(payload.get("url") or "")
        if message.scenario == "task_due_today":
            return self._task_due_today(payload=payload, url=url)
        if message.scenario == "project_pending_review":
            return self._project_pending_review(payload=payload, url=url)
        return self._default_message(message=message, url=url)

    @staticmethod
    def _task_due_today(*, payload: dict[str, object], url: str) -> str:
        task_no = str(payload.get("task_no") or "未编号任务")
        title = str(payload.get("title") or "未命名任务")
        due_date = str(payload.get("due_date") or "今天")
        lines = [
            "### 任务今日到期",
            f"> 任务：{task_no} {title}",
            f"> 截止日期：{due_date}",
        ]
        if url:
            lines.append(f"[查看任务]({url})")
        return "\n".join(lines)

    @staticmethod
    def _project_pending_review(*, payload: dict[str, object], url: str) -> str:
        project_no = str(payload.get("project_no") or "未编号项目")
        project_name = str(payload.get("project_name") or "未命名项目")
        lines = [
            "### 项目待审核",
            f"> 项目：{project_no} {project_name}",
        ]
        if url:
            lines.append(f"[进入审核]({url})")
        return "\n".join(lines)

    @staticmethod
    def _default_message(*, message: NotificationChannelMessage, url: str) -> str:
        lines = [
            "### 项目管理系统通知",
            f"> 场景：{message.scenario}",
            f"> 来源：{message.source_id}",
        ]
        if url:
            lines.append(f"[查看详情]({url})")
        return "\n".join(lines)
