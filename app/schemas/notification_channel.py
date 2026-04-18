from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProjectNotificationChannelCreate(BaseModel):
    channel_type: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=255)
    secret_ref: str | None = Field(default=None, min_length=1, max_length=255)
    is_enabled: bool = True


class ProjectNotificationChannelUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    secret_ref: str | None = Field(default=None, min_length=1, max_length=255)
    is_enabled: bool | None = None


class ProjectNotificationChannelRead(ORMModel):
    id: int
    project_id: int
    channel_type: str
    display_name: str
    secret_ref: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
