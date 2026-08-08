"""
Run with: python -m app.workers.run_once
(or, against the running stack: docker compose exec worker python -m app.workers.run_once)

Triggers exactly one aggregation run immediately and exits. Exists because
the scheduled worker (aggregation_job.py) only runs immediately at
container startup and then every RUN_INTERVAL_HOURS — if you generate new
traffic AFTER that startup run, you'd otherwise have to wait a full hour
(or restart the worker container) to see it reflected. This is the
"give me a result right now" escape hatch for development; the real
scheduled worker is still what runs in production.
"""
from datetime import datetime, timezone

from app.core.logging import configure_logging, get_logger
from app.db.clickhouse import get_client
from app.services.aggregation_service import run_aggregation_job
from app.services.job_run_logger import log_job_run

configure_logging()
logger = get_logger(__name__)

JOB_NAME = "ad_spend_aggregation"


def main() -> None:
    client = get_client()
    started_at = datetime.now(timezone.utc)
    try:
        summary = run_aggregation_job(client)
        finished_at = datetime.now(timezone.utc)
        log_job_run(
            client, JOB_NAME, started_at, finished_at, summary.advertisers_processed, "success"
        )
        logger.info(
            "Manual aggregation run complete: %d advertiser(s) processed in %.2fs (%s)",
            summary.advertisers_processed,
            summary.duration_seconds,
            summary.advertiser_ids,
        )
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        log_job_run(client, JOB_NAME, started_at, finished_at, 0, "failed", str(exc))
        logger.exception("Manual aggregation run failed")
        raise


if __name__ == "__main__":
    main()
