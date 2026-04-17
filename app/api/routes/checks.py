from fastapi import APIRouter, Depends
from sqlalchemy import desc, select, true
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
    latest_check_subquery = (
        select(
            CheckResult.id.label("id"),
            CheckResult.service_id.label("service_id"),
            CheckResult.is_success.label("is_success"),
            CheckResult.status_code.label("status_code"),
            CheckResult.response_time_ms.label("response_time_ms"),
            CheckResult.error_message.label("error_message"),
            CheckResult.checked_at.label("checked_at"),
        )
        .where(CheckResult.service_id == Service.id)
        .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
        .limit(1)
        .lateral()
    )

    statement = (
        select(
            Service.id.label("service_id"),
            Service.name.label("service_name"),
            Service.url.label("url"),
            Service.environment.label("environment"),
            Service.is_active.label("is_active"),
            latest_check_subquery.c.id.label("check_id"),
            latest_check_subquery.c.is_success.label("check_is_success"),
            latest_check_subquery.c.status_code.label("check_status_code"),
            latest_check_subquery.c.response_time_ms.label("check_response_time_ms"),
            latest_check_subquery.c.error_message.label("check_error_message"),
            latest_check_subquery.c.checked_at.label("check_checked_at"),
        )
        .select_from(Service)
        .outerjoin(latest_check_subquery, true())
        .where(Service.project_id == project.id)
        .order_by(Service.created_at.asc())
    )
    rows = db.execute(statement).all()

    summaries: list[DashboardServiceSummary] = []
    failure_count = 0

    for row in rows:
        latest_result = None
        if row.check_id is not None:
            latest_result = CheckResultRead(
                id=row.check_id,
                service_id=row.service_id,
                is_success=row.check_is_success,
                status_code=row.check_status_code,
                response_time_ms=row.check_response_time_ms,
                error_message=row.check_error_message,
                checked_at=row.check_checked_at,
            )

        if latest_result is not None and not latest_result.is_success:
            failure_count += 1

        summaries.append(
            DashboardServiceSummary(
                service_id=row.service_id,
                service_name=row.service_name,
                url=row.url,
                environment=row.environment,
                is_active=row.is_active,
                latest_check=latest_result,
            )
        )

    return DashboardRead(
        project_id=project.id,
        project_name=project.name,
        total_services=len(rows),
        active_services=len([row for row in rows if row.is_active]),
        failing_services=failure_count,
        services=summaries,
    )
