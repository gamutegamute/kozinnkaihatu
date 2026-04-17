from __future__ import annotations

from alembic import op


revision = "0002_add_check_results_latest_lookup_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_check_results_service_id_checked_at_desc
        ON check_results (service_id, checked_at DESC, id DESC)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_check_results_service_id_checked_at_desc", table_name="check_results")
