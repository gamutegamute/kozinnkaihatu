from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.check_result import CheckResult
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


def get_notifier() -> Notifier:
    backend = settings.notification_backend.lower().strip()
    if backend == "webhook":
        if not settings.notification_webhook_url:
            raise ValueError("NOTIFICATION_WEBHOOK_URL is required when NOTIFICATION_BACKEND=webhook")
        return WebhookNotifier(settings.notification_webhook_url)
    return LogNotifier()


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
    notifier: Notifier,
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
    notifier.send(payload)

    state.last_notified_status = current_status
    state.last_notification_at = now
    db.add(state)
