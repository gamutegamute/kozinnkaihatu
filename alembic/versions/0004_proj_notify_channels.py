from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_proj_notify"
down_revision = "0003_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_project_notification_channels_project_id",
        "project_notification_channels",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_notification_channels_project_id", table_name="project_notification_channels")
    op.drop_table("project_notification_channels")
