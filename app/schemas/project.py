from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectRead(ORMModel):
    id: int
    name: str
    created_by: int
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectRead):
    pass
