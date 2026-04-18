from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.check_result import CheckResult
from app.models.project_notification_channel import ProjectNotificationChannel
from app.models.service import Service
from app.models.service_notification_state import ServiceNotificationState

logger = logging.getLogger("monitoring_worker.notifications")

STATUS_HEALTHY = "healthy"
STATUS_FAILED = "failed"


@dataclass
class NotificationPayload:
    event_type: str
    service_id: int
    service_name: str
    project_name: str
    url: str
    environment: str
    checked_at: datetime
    is_success: bool
    status_code: int | None
    response_time_ms: int | None
    error_message: str | None

    def as_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "project_name": self.project_name,
            "url": self.url,
            "environment": self.environment,
            "checked_at": self.checked_at.isoformat(),
            "is_success": self.is_success,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
        }


class Notifier(Protocol):
    def send(self, payload: NotificationPayload) -> None: ...


class LogNotifier:
    def send(self, payload: NotificationPayload) -> None:
        logger.warning("Notification event=%s payload=%s", payload.event_type, payload.as_dict())


class WebhookNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, payload: NotificationPayload) -> None:
        with httpx.Client(timeout=settings.notification_timeout_seconds) as client:
            response = client.post(self.webhook_url, json=payload.as_dict())
            response.raise_for_status()


class DiscordNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, payload: NotificationPayload) -> None:
        discord_payload = {
            "content": format_discord_message(payload),
        }
        with httpx.Client(timeout=settings.notification_timeout_seconds) as client:
            response = client.post(self.webhook_url, json=discord_payload)
            response.raise_for_status()


def format_discord_message(payload: NotificationPayload) -> str:
    title = "ALERT: service check failed" if payload.event_type == "failure" else "RECOVERY: service is healthy again"
    status_text = "FAILED" if payload.event_type == "failure" else "RECOVERED"
    status_code = payload.status_code if payload.status_code is not None else "n/a"
    response_time = f"{payload.response_time_ms} ms" if payload.response_time_ms is not None else "n/a"
    error_message = payload.error_message or "-"
    return (
        f"**{title}**\n"
        f"Project: `{payload.project_name}`\n"
        f"Service: `{payload.service_name}`\n"
        f"Environment: `{payload.environment}`\n"
        f"URL: {payload.url}\n"
        f"Status: `{status_text}`\n"
        f"HTTP status: `{status_code}`\n"
        f"Response time: `{response_time}`\n"
        f"Checked at: `{payload.checked_at.isoformat()}`\n"
        f"Error: `{error_message}`"
    )


def build_notifier_for_channel(channel: ProjectNotificationChannel) -> Notifier:
    channel_type = channel.channel_type.lower().strip()
    if channel_type == "log":
        return LogNotifier()
    if channel_type == "discord":
        if not channel.secret_ref:
            raise ValueError("secret_ref is required for discord channels")
        webhook_url = os.getenv(channel.secret_ref)
        if not webhook_url:
            raise ValueError(f"Environment variable '{channel.secret_ref}' is not set")
        return DiscordNotifier(webhook_url)
    if channel_type == "webhook":
        if not channel.secret_ref:
            raise ValueError("secret_ref is required for webhook channels")
        webhook_url = os.getenv(channel.secret_ref)
        if not webhook_url:
            raise ValueError(f"Environment variable '{channel.secret_ref}' is not set")
        return WebhookNotifier(webhook_url)
    raise ValueError(f"Unsupported channel_type '{channel.channel_type}'")


def get_project_notification_channels(db: Session, project_id: int) -> list[ProjectNotificationChannel]:
    statement = (
        select(ProjectNotificationChannel)
        .where(
            ProjectNotificationChannel.project_id == project_id,
            ProjectNotificationChannel.is_enabled.is_(True),
        )
        .order_by(ProjectNotificationChannel.created_at.asc())
    )
    channels = list(db.scalars(statement).all())
    if channels:
        return channels

    default_backend = settings.notification_backend.lower().strip()
    if default_backend == "log":
        return [
            ProjectNotificationChannel(
                project_id=project_id,
                channel_type="log",
                display_name="default-log",
                is_enabled=True,
            )
        ]
    if default_backend == "discord" and settings.notification_discord_webhook_url:
        return [
            ProjectNotificationChannel(
                project_id=project_id,
                channel_type="discord",
                display_name="default-discord",
                secret_ref="NOTIFICATION_DISCORD_WEBHOOK_URL",
                is_enabled=True,
            )
        ]
    if default_backend == "webhook" and settings.notification_webhook_url:
        return [
            ProjectNotificationChannel(
                project_id=project_id,
                channel_type="webhook",
                display_name="default-webhook",
                secret_ref="NOTIFICATION_WEBHOOK_URL",
                is_enabled=True,
            )
        ]
    return []


def get_or_create_notification_state(db: Session, service_id: int) -> ServiceNotificationState:
    state = db.scalar(
        select(ServiceNotificationState).where(ServiceNotificationState.service_id == service_id)
    )
    if state is None:
        state = ServiceNotificationState(service_id=service_id)
        db.add(state)
        db.flush()
    return state


def evaluate_and_send_notification(
    db: Session,
    service: Service,
    result: CheckResult,
) -> None:
    state = get_or_create_notification_state(db=db, service_id=service.id)
    now = datetime.now(timezone.utc)
    current_status = STATUS_HEALTHY if result.is_success else STATUS_FAILED
    previous_status = state.last_observed_status
    should_notify = False
    event_type: str | None = None

    if current_status == STATUS_FAILED and state.last_notified_status != STATUS_FAILED:
        should_notify = True
        event_type = "failure"
        state.last_failure_at = now
    elif previous_status == STATUS_FAILED and current_status == STATUS_HEALTHY and state.last_notified_status != STATUS_HEALTHY:
        should_notify = True
        event_type = "recovery"
        state.last_recovery_at = now

    state.last_observed_status = current_status

    if not should_notify or event_type is None:
        db.add(state)
        return

    payload = NotificationPayload(
        event_type=event_type,
        service_id=service.id,
        service_name=service.name,
        project_name=service.project.name,
        url=service.url,
        environment=service.environment,
        checked_at=result.checked_at,
        is_success=result.is_success,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        error_message=result.error_message,
    )

    channels = get_project_notification_channels(db=db, project_id=service.project_id)
    if not channels:
        logger.info("No enabled notification channels for project_id=%s", service.project_id)
    for channel in channels:
        notifier = build_notifier_for_channel(channel)
        notifier.send(payload)

    state.last_notified_status = current_status
    state.last_notification_at = now
    db.add(state)
