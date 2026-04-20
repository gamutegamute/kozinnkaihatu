from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.check_result import CheckResult
from app.models.notification_event import NotificationEvent
from app.models.project_notification_channel import ProjectNotificationChannel
from app.models.service import Service
from app.models.service_notification_state import ServiceNotificationState
from worker.secrets import SecretResolver, get_secret_resolver

logger = logging.getLogger("monitoring_worker.notifications")

STATUS_HEALTHY = "healthy"
STATUS_FAILED = "failed"
EVENT_FAILURE = "failure"
EVENT_RECOVERY = "recovery"
DELIVERY_PENDING = "pending"
DELIVERY_SENT = "sent"
DELIVERY_FAILED = "failed"
DISCORD_MAX_RETRIES = 3


@dataclass
class NotificationPayload:
    project_id: int
    service_id: int
    check_result_id: int | None
    event_type: str
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
            "project_id": self.project_id,
            "service_id": self.service_id,
            "check_result_id": self.check_result_id,
            "event_type": self.event_type,
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
        try:
            with httpx.Client(timeout=settings.notification_timeout_seconds) as client:
                response = client.post(self.webhook_url, json=payload.as_dict())
                response.raise_for_status()
        except Exception:
            logger.exception(
                "Generic webhook notification send failed for project=%s service=%s event=%s",
                payload.project_name,
                payload.service_name,
                payload.event_type,
            )
            raise


class DiscordNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, payload: NotificationPayload) -> None:
        try:
            with httpx.Client(timeout=settings.notification_timeout_seconds) as client:
                for attempt in range(1, DISCORD_MAX_RETRIES + 1):
                    response = client.post(self.webhook_url, json=self._build_embed_payload(payload))
                    if response.status_code != 429:
                        response.raise_for_status()
                        return

                    retry_after = self._parse_retry_after_seconds(response)
                    logger.warning(
                        "Discord webhook rate limited on attempt=%s retry_after=%ss service=%s",
                        attempt,
                        retry_after,
                        payload.service_name,
                    )
                    if attempt == DISCORD_MAX_RETRIES:
                        response.raise_for_status()
                    time.sleep(retry_after)
        except Exception:
            logger.exception(
                "Discord notification send failed for project=%s service=%s event=%s",
                payload.project_name,
                payload.service_name,
                payload.event_type,
            )
            raise

    def _build_embed_payload(self, payload: NotificationPayload) -> dict:
        return {
            "embeds": [
                {
                    "title": self._embed_title(payload),
                    "color": self._embed_color(payload),
                    "fields": self._embed_fields(payload),
                    "timestamp": payload.checked_at.isoformat(),
                }
            ]
        }

    def _embed_title(self, payload: NotificationPayload) -> str:
        return "Service check failed" if payload.event_type == EVENT_FAILURE else "Service recovered"

    def _embed_color(self, payload: NotificationPayload) -> int:
        return 15158332 if payload.event_type == EVENT_FAILURE else 3066993

    def _embed_fields(self, payload: NotificationPayload) -> list[dict[str, object]]:
        fields: list[dict[str, object]] = [
            {"name": "Project", "value": payload.project_name, "inline": True},
            {"name": "Service", "value": payload.service_name, "inline": True},
            {"name": "Status", "value": "FAIL" if payload.event_type == EVENT_FAILURE else "RECOVERY", "inline": True},
            {"name": "Environment", "value": payload.environment, "inline": True},
            {"name": "Checked At", "value": payload.checked_at.isoformat(), "inline": False},
        ]
        if payload.status_code is not None:
            fields.append({"name": "HTTP Status", "value": str(payload.status_code), "inline": True})
        if payload.response_time_ms is not None:
            fields.append({"name": "Response Time", "value": f"{payload.response_time_ms} ms", "inline": True})
        if payload.event_type == EVENT_FAILURE and payload.error_message:
            fields.append({"name": "Error", "value": payload.error_message[:1024], "inline": False})
        return fields

    def _parse_retry_after_seconds(self, response: httpx.Response) -> float:
        retry_after_header = response.headers.get("Retry-After")
        if retry_after_header is not None:
            try:
                return max(0.0, float(retry_after_header))
            except ValueError:
                logger.warning("Invalid Retry-After header received from Discord: %s", retry_after_header)
        try:
            retry_after_body = response.json().get("retry_after")
            if retry_after_body is not None:
                return max(0.0, float(retry_after_body))
        except Exception:
            logger.warning("Failed to parse Discord 429 response body")
        return 1.0


def _build_log_notifier(channel: ProjectNotificationChannel, secret_resolver: SecretResolver) -> Notifier:
    return LogNotifier()


def _build_discord_notifier(channel: ProjectNotificationChannel, secret_resolver: SecretResolver) -> Notifier:
    if not channel.secret_ref:
        raise ValueError("secret_ref is required for discord channels")
    webhook_url = secret_resolver.resolve(channel.secret_ref)
    if not webhook_url:
        raise ValueError(f"Secret '{channel.secret_ref}' is not available")
    return DiscordNotifier(webhook_url)


def _build_webhook_notifier(channel: ProjectNotificationChannel, secret_resolver: SecretResolver) -> Notifier:
    if not channel.secret_ref:
        raise ValueError("secret_ref is required for webhook channels")
    webhook_url = secret_resolver.resolve(channel.secret_ref)
    if not webhook_url:
        raise ValueError(f"Secret '{channel.secret_ref}' is not available")
    return WebhookNotifier(webhook_url)


NOTIFIER_BUILDERS: dict[str, Callable[[ProjectNotificationChannel, SecretResolver], Notifier]] = {
    "log": _build_log_notifier,
    "discord": _build_discord_notifier,
    "webhook": _build_webhook_notifier,
}


def build_notifier_for_channel(channel: ProjectNotificationChannel, secret_resolver: SecretResolver) -> Notifier:
    channel_type = channel.channel_type.lower().strip()
    builder = NOTIFIER_BUILDERS.get(channel_type)
    if builder is None:
        raise ValueError(f"Unsupported channel_type '{channel.channel_type}'")
    return builder(channel, secret_resolver)


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


def create_notification_event(
    db: Session,
    channel: ProjectNotificationChannel,
    payload: NotificationPayload,
) -> NotificationEvent:
    event = NotificationEvent(
        project_id=payload.project_id,
        service_id=payload.service_id,
        channel_id=channel.id,
        check_result_id=payload.check_result_id,
        channel_type=channel.channel_type,
        channel_display_name=channel.display_name,
        event_type=payload.event_type,
        delivery_status=DELIVERY_PENDING,
    )
    db.add(event)
    db.flush()
    return event


def mark_notification_event_sent(db: Session, event: NotificationEvent) -> None:
    event.delivery_status = DELIVERY_SENT
    event.delivered_at = datetime.now(timezone.utc)
    event.error_message = None
    db.add(event)


def mark_notification_event_failed(db: Session, event: NotificationEvent, error_message: str) -> None:
    event.delivery_status = DELIVERY_FAILED
    event.error_message = error_message
    db.add(event)


def dispatch_notification_for_channel(
    db: Session,
    channel: ProjectNotificationChannel,
    payload: NotificationPayload,
    secret_resolver: SecretResolver,
) -> NotificationEvent:
    event = create_notification_event(db=db, channel=channel, payload=payload)
    try:
        notifier = build_notifier_for_channel(channel, secret_resolver=secret_resolver)
        notifier.send(payload)
    except Exception as exc:
        mark_notification_event_failed(db=db, event=event, error_message=str(exc))
        logger.exception(
            "Notification dispatch failed for project=%s service=%s channel=%s event=%s",
            payload.project_name,
            payload.service_name,
            channel.display_name,
            payload.event_type,
        )
        return event

    mark_notification_event_sent(db=db, event=event)
    return event


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
        event_type = EVENT_FAILURE
        state.last_failure_at = now
    elif previous_status == STATUS_FAILED and current_status == STATUS_HEALTHY and state.last_notified_status != STATUS_HEALTHY:
        should_notify = True
        event_type = EVENT_RECOVERY
        state.last_recovery_at = now

    state.last_observed_status = current_status

    if not should_notify or event_type is None:
        db.add(state)
        return

    payload = NotificationPayload(
        project_id=service.project_id,
        service_id=service.id,
        check_result_id=result.id,
        event_type=event_type,
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

    secret_resolver = get_secret_resolver()
    for channel in channels:
        dispatch_notification_for_channel(
            db=db,
            channel=channel,
            payload=payload,
            secret_resolver=secret_resolver,
        )

    state.last_notified_status = current_status
    state.last_notification_at = now
    db.add(state)
