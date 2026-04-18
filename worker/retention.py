from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.check_result import CheckResult

logger = logging.getLogger("monitoring_worker.retention")


def retention_cutoff(now: datetime | None = None) -> datetime:
    current_time = now or datetime.now(timezone.utc)
    return current_time - timedelta(days=settings.check_results_retention_days)


def cleanup_old_check_results(db: Session, now: datetime | None = None) -> int:
    cutoff = retention_cutoff(now=now)
    total_deleted = 0

    while True:
        old_ids = list(
            db.scalars(
                select(CheckResult.id)
                .where(CheckResult.checked_at < cutoff)
                .order_by(CheckResult.checked_at.asc(), CheckResult.id.asc())
                .limit(settings.retention_delete_batch_size)
            ).all()
        )

        if not old_ids:
            break

        deleted_count = db.execute(delete(CheckResult).where(CheckResult.id.in_(old_ids))).rowcount or 0
        db.commit()
        total_deleted += deleted_count

        logger.info(
            "Deleted %s old check_results rows in this batch (cutoff=%s)",
            deleted_count,
            cutoff.isoformat(),
        )

        if deleted_count < settings.retention_delete_batch_size:
            break

    return total_deleted
