from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field

from app.schemas.common import ORMModel


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: AnyHttpUrl
    environment: str = Field(min_length=1, max_length=50)
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: AnyHttpUrl | None = None
    environment: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class ServiceRead(ORMModel):
    id: int
    project_id: int
    name: str
    url: str
    environment: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
