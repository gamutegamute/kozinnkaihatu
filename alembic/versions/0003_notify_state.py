from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_notify"
down_revision = "0002_latest_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_notification_states",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_observed_status", sa.String(length=20), nullable=True),
        sa.Column("last_notified_status", sa.String(length=20), nullable=True),
        sa.Column("last_notification_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_recovery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_service_notification_states_service_id",
        "service_notification_states",
        ["service_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_service_notification_states_service_id", table_name="service_notification_states")
    op.drop_table("service_notification_states")
