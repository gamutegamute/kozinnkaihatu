from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.notification_event import NotificationEvent
from app.models.service import Service


@dataclass
class PaginatedResult:
    total: int
    items: list


def list_project_notification_events(
    db: Session,
    project_id: int,
    *,
    service_id: int | None,
    delivery_status: str | None,
    event_type: str | None,
    limit: int,
    offset: int,
) -> PaginatedResult:
    filters = [NotificationEvent.project_id == project_id]
    if service_id is not None:
        filters.append(NotificationEvent.service_id == service_id)
    if delivery_status is not None:
        filters.append(NotificationEvent.delivery_status == delivery_status)
    if event_type is not None:
        filters.append(NotificationEvent.event_type == event_type)

    count_statement = select(func.count(NotificationEvent.id)).where(*filters)
    total = db.scalar(count_statement) or 0

    statement: Select = (
        select(
            NotificationEvent,
            Service.name.label("service_name"),
        )
        .join(Service, Service.id == NotificationEvent.service_id)
        .where(*filters)
        .order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return PaginatedResult(total=total, items=list(db.execute(statement).all()))


def list_project_incidents(
    db: Session,
    project_id: int,
    *,
    service_id: int | None,
    status: str | None,
    limit: int,
    offset: int,
) -> PaginatedResult:
    filters = [Incident.project_id == project_id]
    if service_id is not None:
        filters.append(Incident.service_id == service_id)
    if status is not None:
        filters.append(Incident.status == status)

    count_statement = select(func.count(Incident.id)).where(*filters)
    total = db.scalar(count_statement) or 0

    statement: Select = (
        select(
            Incident,
            Service.name.label("service_name"),
        )
        .join(Service, Service.id == Incident.service_id)
        .where(*filters)
        .order_by(Incident.opened_at.desc(), Incident.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return PaginatedResult(total=total, items=list(db.execute(statement).all()))
