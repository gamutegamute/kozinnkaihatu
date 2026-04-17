from datetime import datetime

from app.schemas.common import ORMModel


class CheckResultRead(ORMModel):
    id: int
    service_id: int
    is_success: bool
    status_code: int | None
    response_time_ms: int | None
    error_message: str | None
    checked_at: datetime


class DashboardServiceSummary(ORMModel):
    service_id: int
    service_name: str
    environment: str
    is_active: bool
    latest_check: CheckResultRead | None


class DashboardRead(ORMModel):
    project_id: int
    project_name: str
    total_services: int
    active_services: int
    failing_services: int
    services: list[DashboardServiceSummary]
