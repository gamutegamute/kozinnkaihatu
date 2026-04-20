from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.check_result import CheckResult
from app.models.incident import Incident
from app.models.service import Service
from app.models.service_notification_state import ServiceNotificationState

STATUS_HEALTHY = "healthy"
STATUS_FAILED = "failed"
INCIDENT_OPEN = "open"
INCIDENT_CLOSED = "closed"


def get_or_create_notification_state(db: Session, service_id: int) -> ServiceNotificationState:
    state = db.scalar(
        select(ServiceNotificationState).where(ServiceNotificationState.service_id == service_id)
    )
    if state is None:
        state = ServiceNotificationState(service_id=service_id)
        db.add(state)
        db.flush()
    return state


def get_open_incident(db: Session, service_id: int) -> Incident | None:
    return db.scalar(
        select(Incident)
        .where(Incident.service_id == service_id, Incident.closed_at.is_(None))
        .order_by(Incident.opened_at.desc(), Incident.id.desc())
    )


def reconcile_incident_state(db: Session, service: Service, result: CheckResult) -> None:
    state = get_or_create_notification_state(db=db, service_id=service.id)
    previous_status = state.last_observed_status
    current_status = STATUS_HEALTHY if result.is_success else STATUS_FAILED

    if current_status == STATUS_FAILED and previous_status != STATUS_FAILED:
        open_incident = get_open_incident(db=db, service_id=service.id)
        if open_incident is None:
            db.add(
                Incident(
                    project_id=service.project_id,
                    service_id=service.id,
                    opened_check_result_id=result.id,
                    title=f"{service.name} is failing",
                    status=INCIDENT_OPEN,
                    opened_at=result.checked_at,
                )
            )
        return

    if current_status == STATUS_HEALTHY and previous_status == STATUS_FAILED:
        open_incident = get_open_incident(db=db, service_id=service.id)
        if open_incident is not None:
            open_incident.status = INCIDENT_CLOSED
            open_incident.closed_at = result.checked_at
            open_incident.closed_check_result_id = result.id
            db.add(open_incident)
