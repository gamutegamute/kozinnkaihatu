from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_project_member, require_project_owner
from app.db.session import get_db
from app.models.project import Project
from app.models.project_notification_channel import ProjectNotificationChannel
from app.schemas.notification_channel import (
    ProjectNotificationChannelCreate,
    ProjectNotificationChannelRead,
    ProjectNotificationChannelUpdate,
)

router = APIRouter()

SUPPORTED_CHANNEL_TYPES = {"log", "webhook", "discord"}


@router.post(
    "/{project_id}/notification-channels",
    response_model=ProjectNotificationChannelRead,
    status_code=status.HTTP_201_CREATED,
)
def create_notification_channel(
    payload: ProjectNotificationChannelCreate,
    project: Project = Depends(require_project_owner),
    db: Session = Depends(get_db),
) -> ProjectNotificationChannel:
    channel_type = payload.channel_type.lower().strip()
    if channel_type not in SUPPORTED_CHANNEL_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported channel_type")

    if channel_type in {"webhook", "discord"} and not payload.secret_ref:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="secret_ref is required")

    channel = ProjectNotificationChannel(
        project_id=project.id,
        channel_type=channel_type,
        display_name=payload.display_name,
        secret_ref=payload.secret_ref,
        is_enabled=payload.is_enabled,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{project_id}/notification-channels", response_model=list[ProjectNotificationChannelRead])
def list_notification_channels(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> list[ProjectNotificationChannel]:
    statement = (
        select(ProjectNotificationChannel)
        .where(ProjectNotificationChannel.project_id == project.id)
        .order_by(ProjectNotificationChannel.created_at.asc())
    )
    return list(db.scalars(statement).all())


@router.patch(
    "/{project_id}/notification-channels/{channel_id}",
    response_model=ProjectNotificationChannelRead,
)
def update_notification_channel(
    payload: ProjectNotificationChannelUpdate,
    project: Project = Depends(require_project_owner),
    db: Session = Depends(get_db),
    channel_id: int = 0,
) -> ProjectNotificationChannel:
    channel = db.scalar(
        select(ProjectNotificationChannel).where(
            ProjectNotificationChannel.id == channel_id,
            ProjectNotificationChannel.project_id == project.id,
        )
    )
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification channel not found")

    update_data = payload.model_dump(exclude_unset=True)
    if channel.channel_type in {"webhook", "discord"}:
        next_secret_ref = update_data.get("secret_ref", channel.secret_ref)
        if not next_secret_ref:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="secret_ref is required")

    for field, value in update_data.items():
        setattr(channel, field, value)

    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel
