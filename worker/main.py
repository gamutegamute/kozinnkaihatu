from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import ServiceNotificationState  # noqa: F401
from app.models.check_result import CheckResult
from app.models.service import Service
from worker.notifications import evaluate_and_send_notification, get_notifier
from worker.retention import cleanup_old_check_results

logger = logging.getLogger("monitoring_worker")

SUCCESS_STATUS_MIN = 200
SUCCESS_STATUS_MAX_EXCLUSIVE = 400


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def monitor_service(client: httpx.Client, service: Service) -> CheckResult:
    started_at = time.perf_counter()

    try:
        response = client.get(service.url, timeout=settings.request_timeout_seconds)
        response_time_ms = int((time.perf_counter() - started_at) * 1000)
        is_success = SUCCESS_STATUS_MIN <= response.status_code < SUCCESS_STATUS_MAX_EXCLUSIVE

        return CheckResult(
            service_id=service.id,
            is_success=is_success,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            error_message=None,
            checked_at=datetime.now(timezone.utc),
        )
    except httpx.TimeoutException as exc:
        response_time_ms = int((time.perf_counter() - started_at) * 1000)
        return CheckResult(
            service_id=service.id,
            is_success=False,
            status_code=None,
            response_time_ms=response_time_ms,
            error_message=f"Timeout after {settings.request_timeout_seconds} seconds: {exc.__class__.__name__}",
            checked_at=datetime.now(timezone.utc),
        )
    except httpx.HTTPError as exc:
        response_time_ms = int((time.perf_counter() - started_at) * 1000)
        return CheckResult(
            service_id=service.id,
            is_success=False,
            status_code=None,
            response_time_ms=response_time_ms,
            error_message=str(exc),
            checked_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        response_time_ms = int((time.perf_counter() - started_at) * 1000)
        return CheckResult(
            service_id=service.id,
            is_success=False,
            status_code=None,
            response_time_ms=response_time_ms,
            error_message=f"Unexpected error: {exc}",
            checked_at=datetime.now(timezone.utc),
        )


def run_monitoring_cycle() -> None:
    with SessionLocal() as db:
        notifier = get_notifier()
        services = list(
            db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.id.asc())).all()
        )
        logger.info("Starting monitoring cycle for %s active services", len(services))

        with httpx.Client(follow_redirects=True) as client:
            for service in services:
                result = monitor_service(client=client, service=service)
                db.add(result)
                db.commit()
                db.refresh(result)

                try:
                    evaluate_and_send_notification(db=db, notifier=notifier, service=service, result=result)
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Notification dispatch failed for service_id=%s", service.id)

                logger.info(
                    "Checked service_id=%s url=%s success=%s status_code=%s response_time_ms=%s",
                    service.id,
                    service.url,
                    result.is_success,
                    result.status_code,
                    result.response_time_ms,
                )
        logger.info("Monitoring cycle completed")


def run_retention_cleanup() -> None:
    with SessionLocal() as db:
        deleted_rows = cleanup_old_check_results(db=db)
        logger.info(
            "Retention cleanup completed: deleted_rows=%s retention_days=%s",
            deleted_rows,
            settings.check_results_retention_days,
        )


def main() -> None:
    configure_logging()
    logger.info(
        "Monitoring worker started with interval=%ss timeout=%ss retention_days=%s cleanup_interval_hours=%s",
        settings.monitor_interval_seconds,
        settings.request_timeout_seconds,
        settings.check_results_retention_days,
        settings.retention_cleanup_interval_hours,
    )
    next_retention_run_at = datetime.now(timezone.utc)

    while True:
        cycle_started_at = time.perf_counter()

        try:
            run_monitoring_cycle()
            current_time = datetime.now(timezone.utc)
            if current_time >= next_retention_run_at:
                run_retention_cleanup()
                next_retention_run_at = current_time + timedelta(hours=settings.retention_cleanup_interval_hours)
        except Exception:
            logger.exception("Monitoring cycle failed")

        elapsed_seconds = time.perf_counter() - cycle_started_at
        sleep_seconds = max(0, settings.monitor_interval_seconds - elapsed_seconds)
        logger.info("Sleeping for %.2f seconds", sleep_seconds)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
