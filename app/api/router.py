from fastapi import APIRouter

from app.api.routes import auth, checks, members, notification_channels, projects, services

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(members.router, prefix="/projects", tags=["members"])
api_router.include_router(notification_channels.router, prefix="/projects", tags=["notification-channels"])
api_router.include_router(services.router, tags=["services"])
api_router.include_router(checks.router, tags=["checks"])
