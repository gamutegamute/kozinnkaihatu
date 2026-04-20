from datetime import datetime

from app.schemas.common import ORMModel


class NotificationEventListItem(ORMModel):
    id: int
    project_id: int
    service_id: int
    service_name: str
    channel_id: int | None
    channel_type: str
    channel_display_name: str
    check_result_id: int | None
    event_type: str
    delivery_status: str
    error_message: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationEventListResponse(ORMModel):
    total: int
    limit: int
    offset: int
    items: list[NotificationEventListItem]
