from __future__ import annotations

import asyncio
import smtplib
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.users import User
from app.services.notification_channels import (
    ChannelDeliveryResult,
    NotificationChannelMessage,
    NotificationChannelType,
)


class EmailRecipientResolver(Protocol):
    async def resolve_email(self, receiver_id: UUID) -> str | None:
        ...


class EmailTransport(Protocol):
    async def send(self, message: EmailMessage) -> ChannelDeliveryResult:
        ...


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    body: str


class InMemoryEmailRecipientResolver:
    def __init__(self, recipients: Mapping[UUID, str]) -> None:
        self._recipients = dict(recipients)

    async def resolve_email(self, receiver_id: UUID) -> str | None:
        return self._recipients.get(receiver_id)


class SqlAlchemyEmailRecipientResolver:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_email(self, receiver_id: UUID) -> str | None:
        user = await self._session.scalar(select(User).where(User.id == receiver_id))
        return user.email if user is not None else None


class SmtpEmailTransport:
    def __init__(self, settings: Settings, *, timeout_seconds: float = 10.0) -> None:
        self._settings = settings
        self._timeout_seconds = timeout_seconds

    async def send(self, message: EmailMessage) -> ChannelDeliveryResult:
        if not self._settings.smtp_enabled:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.email,
                success=False,
                error="SMTP email channel is disabled",
            )
        if not self._settings.smtp_host:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.email,
                success=False,
                error="SMTP host is not configured",
            )

        try:
            await asyncio.to_thread(self._send_sync, message)
        except (OSError, smtplib.SMTPException) as exc:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.email,
                success=False,
                error=str(exc),
            )
        return ChannelDeliveryResult(channel=NotificationChannelType.email, success=True)

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(
            self._settings.smtp_host,
            self._settings.smtp_port,
            timeout=self._timeout_seconds,
        ) as smtp:
            if self._settings.smtp_use_tls:
                smtp.starttls()
            if self._settings.smtp_username:
                smtp.login(self._settings.smtp_username, self._settings.smtp_password)
            smtp.send_message(message)


class EmailNotificationChannel:
    def __init__(
        self,
        *,
        settings: Settings,
        recipient_resolver: EmailRecipientResolver,
        transport: EmailTransport | None = None,
        template_dir: Path | None = None,
    ) -> None:
        self._settings = settings
        self._recipient_resolver = recipient_resolver
        self._transport = transport or SmtpEmailTransport(settings)
        templates = template_dir or (
            Path(__file__).resolve().parents[1] / "templates" / "notifications" / "email"
        )
        self._templates = Environment(
            loader=FileSystemLoader(str(templates)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def send(self, message: NotificationChannelMessage) -> ChannelDeliveryResult:
        recipient = await self._recipient_resolver.resolve_email(message.receiver_id)
        if recipient is None:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.email,
                success=False,
                error="Recipient email is not configured",
            )
        if not self._settings.smtp_from_address:
            return ChannelDeliveryResult(
                channel=NotificationChannelType.email,
                success=False,
                error="SMTP from address is not configured",
            )

        rendered = self._render(message)
        email = EmailMessage()
        email["From"] = self._settings.smtp_from_address
        email["To"] = recipient
        email["Subject"] = rendered.subject
        email.set_content(rendered.body)
        return await self._transport.send(email)

    def _render(self, message: NotificationChannelMessage) -> RenderedEmail:
        template_name = f"{message.scenario}.j2"
        try:
            template = self._templates.get_template(template_name)
        except TemplateNotFound:
            template = self._templates.get_template("default.j2")

        context = {
            **message.payload,
            "dedup_key": message.dedup_key,
            "payload": message.payload,
            "scenario": message.scenario,
            "source_id": message.source_id,
        }
        return self._parse_rendered_template(template.render(context))

    @staticmethod
    def _parse_rendered_template(rendered: str) -> RenderedEmail:
        stripped = rendered.strip()
        lines = stripped.splitlines()
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0].split(":", maxsplit=1)[1].strip()
            body = "\n".join(lines[1:]).strip()
            return RenderedEmail(subject=subject, body=body)
        return RenderedEmail(subject="项目管理系统通知", body=stripped)
