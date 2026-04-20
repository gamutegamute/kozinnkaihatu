from fastapi import APIRouter

from app.api.routes import auth, checks, incidents, members, notification_channels, notification_events, projects, services

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(members.router, prefix="/projects", tags=["members"])
api_router.include_router(notification_channels.router, prefix="/projects", tags=["notification-channels"])
api_router.include_router(notification_events.router, prefix="/projects", tags=["notification-events"])
api_router.include_router(incidents.router, prefix="/projects", tags=["incidents"])
api_router.include_router(services.router, tags=["services"])
api_router.include_router(checks.router, tags=["checks"])
