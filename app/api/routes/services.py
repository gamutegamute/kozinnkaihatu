from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_service_for_member, require_project_member
from app.db.session import get_db
from app.models.project import Project
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter()


@router.post("/projects/{project_id}/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> Service:
    service = Service(
        project_id=project.id,
        name=payload.name,
        url=str(payload.url),
        environment=payload.environment,
        is_active=payload.is_active,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/projects/{project_id}/services", response_model=list[ServiceRead])
def list_services(project: Project = Depends(require_project_member), db: Session = Depends(get_db)) -> list[Service]:
    statement = select(Service).where(Service.project_id == project.id).order_by(Service.created_at.desc())
    return list(db.scalars(statement).all())


@router.get("/services/{service_id}", response_model=ServiceRead)
def get_service(service: Service = Depends(get_service_for_member)) -> Service:
    return service


@router.patch("/services/{service_id}", response_model=ServiceRead)
def update_service(
    payload: ServiceUpdate,
    service: Service = Depends(get_service_for_member),
    db: Session = Depends(get_db),
) -> Service:
    update_data = payload.model_dump(exclude_unset=True)
    if "url" in update_data and update_data["url"] is not None:
        update_data["url"] = str(update_data["url"])

    for field, value in update_data.items():
        setattr(service, field, value)

    db.add(service)
    db.commit()
    db.refresh(service)
    return service
