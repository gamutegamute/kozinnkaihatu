from __future__ import annotations

import logging

from app.core.config import settings
from app.db.session import SessionLocal
from worker.retention import cleanup_old_check_results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger("monitoring_retention_job")

    with SessionLocal() as db:
        deleted_rows = cleanup_old_check_results(db=db)

    logger.info(
        "Retention job finished: deleted_rows=%s retention_days=%s",
        deleted_rows,
        settings.check_results_retention_days,
    )


if __name__ == "__main__":
    main()
