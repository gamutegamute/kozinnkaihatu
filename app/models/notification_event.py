from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_notification_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    check_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("check_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel_type: Mapped[str] = mapped_column(String(50))
    channel_display_name: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(20), index=True)
    delivery_status: Mapped[str] = mapped_column(String(20), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project", back_populates="notification_events")
    service = relationship("Service", back_populates="notification_events")
    channel = relationship("ProjectNotificationChannel", back_populates="notification_events")
    check_result = relationship("CheckResult", back_populates="notification_events")
