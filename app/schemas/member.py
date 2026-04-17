from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.project_member import ProjectRole
from app.schemas.common import ORMModel


class MemberCreate(BaseModel):
    email: EmailStr
    role: ProjectRole


class MemberRead(ORMModel):
    id: int
    project_id: int
    user_id: int
    role: ProjectRole
    created_at: datetime
