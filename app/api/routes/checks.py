from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_service_for_member, require_project_member
from app.db.session import get_db
from app.models.check_result import CheckResult
from app.models.project import Project
from app.models.service import Service
from app.schemas.check import CheckResultRead, DashboardRead, DashboardServiceSummary

router = APIRouter()


@router.get("/services/{service_id}/checks", response_model=list[CheckResultRead])
def list_service_checks(
    service: Service = Depends(get_service_for_member),
    db: Session = Depends(get_db),
) -> list[CheckResult]:
    statement = (
        select(CheckResult)
        .where(CheckResult.service_id == service.id)
        .order_by(desc(CheckResult.checked_at))
        .limit(100)
    )
    return list(db.scalars(statement).all())


@router.get("/projects/{project_id}/dashboard", response_model=DashboardRead)
def project_dashboard(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> DashboardRead:
    services = list(
        db.scalars(select(Service).where(Service.project_id == project.id).order_by(Service.created_at.asc())).all()
    )

    summaries: list[DashboardServiceSummary] = []
    failure_count = 0

    for service in services:
        latest_result = db.scalar(
            select(CheckResult)
            .where(CheckResult.service_id == service.id)
            .order_by(desc(CheckResult.checked_at))
            .limit(1)
        )
        if latest_result is not None and not latest_result.is_success:
            failure_count += 1

        summaries.append(
            DashboardServiceSummary(
                service_id=service.id,
                service_name=service.name,
                environment=service.environment,
                is_active=service.is_active,
                latest_check=latest_result,
            )
        )

    return DashboardRead(
        project_id=project.id,
        project_name=project.name,
        total_services=len(services),
        active_services=len([service for service in services if service.is_active]),
        failing_services=failure_count,
        services=summaries,
    )
