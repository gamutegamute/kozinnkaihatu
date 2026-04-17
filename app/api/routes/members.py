from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_project_member, require_project_owner
from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.member import MemberCreate, MemberRead

router = APIRouter()


@router.post("/{project_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: MemberCreate,
    project: Project = Depends(require_project_owner),
    db: Session = Depends(get_db),
) -> ProjectMember:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a project member")

    member = ProjectMember(project_id=project.id, user_id=user.id, role=payload.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{project_id}/members", response_model=list[MemberRead])
def list_members(
    project_id: int = Path(..., ge=1),
    _: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> list[ProjectMember]:
    statement = (
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc())
    )
    return list(db.scalars(statement).all())
