from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_project_member
from app.db.session import get_db
from app.models.project import Project
from app.schemas.notification_event import NotificationEventListItem, NotificationEventListResponse
from app.services.notification_queries import list_project_notification_events

router = APIRouter()

SUPPORTED_EVENT_TYPES = {"failure", "recovery"}
SUPPORTED_DELIVERY_STATUSES = {"pending", "sent", "failed"}


@router.get("/{project_id}/notification-events", response_model=NotificationEventListResponse)
def get_project_notification_events(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
    service_id: int | None = Query(default=None, ge=1),
    delivery_status: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationEventListResponse:
    normalized_delivery_status = delivery_status.lower().strip() if delivery_status else None
    if normalized_delivery_status and normalized_delivery_status not in SUPPORTED_DELIVERY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported delivery_status",
        )

    normalized_event_type = event_type.lower().strip() if event_type else None
    if normalized_event_type and normalized_event_type not in SUPPORTED_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported event_type",
        )

    result = list_project_notification_events(
        db=db,
        project_id=project.id,
        service_id=service_id,
        delivery_status=normalized_delivery_status,
        event_type=normalized_event_type,
        limit=limit,
        offset=offset,
    )
    items = [
        NotificationEventListItem(
            id=row.NotificationEvent.id,
            project_id=row.NotificationEvent.project_id,
            service_id=row.NotificationEvent.service_id,
            service_name=row.service_name,
            channel_id=row.NotificationEvent.channel_id,
            channel_type=row.NotificationEvent.channel_type,
            channel_display_name=row.NotificationEvent.channel_display_name,
            check_result_id=row.NotificationEvent.check_result_id,
            event_type=row.NotificationEvent.event_type,
            delivery_status=row.NotificationEvent.delivery_status,
            error_message=row.NotificationEvent.error_message,
            delivered_at=row.NotificationEvent.delivered_at,
            created_at=row.NotificationEvent.created_at,
            updated_at=row.NotificationEvent.updated_at,
        )
        for row in result.items
    ]
    return NotificationEventListResponse(total=result.total, limit=limit, offset=offset, items=items)
