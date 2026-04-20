from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_notify_inc"
down_revision = "0004_proj_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("project_notification_channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "check_result_id",
            sa.Integer(),
            sa.ForeignKey("check_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel_type", sa.String(length=50), nullable=False),
        sa.Column("channel_display_name", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notification_events_project_id", "notification_events", ["project_id"], unique=False)
    op.create_index("ix_notification_events_service_id", "notification_events", ["service_id"], unique=False)
    op.create_index("ix_notification_events_channel_id", "notification_events", ["channel_id"], unique=False)
    op.create_index("ix_notification_events_check_result_id", "notification_events", ["check_result_id"], unique=False)
    op.create_index("ix_notification_events_event_type", "notification_events", ["event_type"], unique=False)
    op.create_index("ix_notification_events_delivery_status", "notification_events", ["delivery_status"], unique=False)
    op.create_index("ix_notification_events_created_at", "notification_events", ["created_at"], unique=False)

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "opened_check_result_id",
            sa.Integer(),
            sa.ForeignKey("check_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "closed_check_result_id",
            sa.Integer(),
            sa.ForeignKey("check_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_incidents_project_id", "incidents", ["project_id"], unique=False)
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"], unique=False)
    op.create_index("ix_incidents_status", "incidents", ["status"], unique=False)
    op.create_index("ix_incidents_opened_at", "incidents", ["opened_at"], unique=False)
    op.create_index("ix_incidents_opened_check_result_id", "incidents", ["opened_check_result_id"], unique=False)
    op.create_index("ix_incidents_closed_check_result_id", "incidents", ["closed_check_result_id"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX ux_incidents_one_open_per_service
        ON incidents (service_id)
        WHERE closed_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ux_incidents_one_open_per_service", table_name="incidents")
    op.drop_index("ix_incidents_closed_check_result_id", table_name="incidents")
    op.drop_index("ix_incidents_opened_check_result_id", table_name="incidents")
    op.drop_index("ix_incidents_opened_at", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_service_id", table_name="incidents")
    op.drop_index("ix_incidents_project_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_notification_events_created_at", table_name="notification_events")
    op.drop_index("ix_notification_events_delivery_status", table_name="notification_events")
    op.drop_index("ix_notification_events_event_type", table_name="notification_events")
    op.drop_index("ix_notification_events_check_result_id", table_name="notification_events")
    op.drop_index("ix_notification_events_channel_id", table_name="notification_events")
    op.drop_index("ix_notification_events_service_id", table_name="notification_events")
    op.drop_index("ix_notification_events_project_id", table_name="notification_events")
    op.drop_table("notification_events")
