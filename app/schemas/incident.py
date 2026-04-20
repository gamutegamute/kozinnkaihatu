from datetime import datetime

from app.schemas.common import ORMModel


class IncidentListItem(ORMModel):
    id: int
    project_id: int
    service_id: int
    service_name: str
    opened_check_result_id: int | None
    closed_check_result_id: int | None
    title: str
    status: str
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentListResponse(ORMModel):
    total: int
    limit: int
    offset: int
    items: list[IncidentListItem]
