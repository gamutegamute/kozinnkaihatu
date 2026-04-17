from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.check_result import CheckResult
from app.models.service import Service

logger = logging.getLogger("monitoring_worker")

CHECK_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 5
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
        response = client.get(service.url, timeout=REQUEST_TIMEOUT_SECONDS)
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
            error_message=f"Timeout after {REQUEST_TIMEOUT_SECONDS} seconds: {exc.__class__.__name__}",
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
        services = list(
            db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.id.asc())).all()
        )
        logger.info("Starting monitoring cycle for %s active services", len(services))

        with httpx.Client(follow_redirects=True) as client:
            for service in services:
                result = monitor_service(client=client, service=service)
                db.add(result)
                db.commit()
                logger.info(
                    "Checked service_id=%s url=%s success=%s status_code=%s response_time_ms=%s",
                    service.id,
                    service.url,
                    result.is_success,
                    result.status_code,
                    result.response_time_ms,
                )
        logger.info("Monitoring cycle completed")


def main() -> None:
    configure_logging()
    logger.info("Monitoring worker started with interval=%ss timeout=%ss", CHECK_INTERVAL_SECONDS, REQUEST_TIMEOUT_SECONDS)

    while True:
        cycle_started_at = time.perf_counter()

        try:
            run_monitoring_cycle()
        except Exception:
            logger.exception("Monitoring cycle failed")

        elapsed_seconds = time.perf_counter() - cycle_started_at
        sleep_seconds = max(0, CHECK_INTERVAL_SECONDS - elapsed_seconds)
        logger.info("Sleeping for %.2f seconds", sleep_seconds)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
