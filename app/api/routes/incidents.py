from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import require_project_member
from app.db.session import get_db
from app.models.project import Project
from app.schemas.incident import IncidentListItem, IncidentListResponse
from app.services.notification_queries import list_project_incidents

router = APIRouter()

SUPPORTED_INCIDENT_STATUSES = {"open", "closed"}


@router.get("/{project_id}/incidents", response_model=IncidentListResponse)
def get_project_incidents(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
    incident_status: str | None = Query(default=None, alias="status"),
    service_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> IncidentListResponse:
    normalized_status = incident_status.lower().strip() if incident_status else None
    if normalized_status and normalized_status not in SUPPORTED_INCIDENT_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported incident status",
        )

    result = list_project_incidents(
        db=db,
        project_id=project.id,
        service_id=service_id,
        status=normalized_status,
        limit=limit,
        offset=offset,
    )
    items = [
        IncidentListItem(
            id=row.Incident.id,
            project_id=row.Incident.project_id,
            service_id=row.Incident.service_id,
            service_name=row.service_name,
            opened_check_result_id=row.Incident.opened_check_result_id,
            closed_check_result_id=row.Incident.closed_check_result_id,
            title=row.Incident.title,
            status=row.Incident.status,
            opened_at=row.Incident.opened_at,
            closed_at=row.Incident.closed_at,
            created_at=row.Incident.created_at,
            updated_at=row.Incident.updated_at,
        )
        for row in result.items
    ]
    return IncidentListResponse(total=result.total, limit=limit, offset=offset, items=items)
