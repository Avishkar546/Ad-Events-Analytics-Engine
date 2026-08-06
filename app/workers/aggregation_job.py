"""
Runs the aggregation job on a schedule using APScheduler — a real scheduling
library instead of a hand-rolled `while True: sleep(3600)` loop.

What APScheduler buys us over a manual loop:
  - misfire_grace_time: if the process was busy/paused and missed its exact
    trigger time, it still runs as long as it's within this grace window,
    instead of silently skipping the run.
  - coalesce: if MULTIPLE runs were missed (e.g. the container was down for
    3 hours), it runs ONCE to catch up, not three times back-to-back — which
    matters here because the job scans a lookback window anyway, so
    replaying missed runs individually would be redundant work.
  - A declarative trigger (IntervalTrigger) instead of manually computing
    "how long until the next run" — less code, fewer off-by-one bugs.

Version note: pinned to APScheduler 3.x (requirements.txt). 4.x is a
significant rewrite of the scheduler's internals — for a project where
correctness matters more than having the newest API, sticking to the
stable, widely-deployed 3.x line is the deliberate choice, not an
oversight.
"""
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.logging import configure_logging, get_logger
from app.db.clickhouse import get_client
from app.services.aggregation_service import run_aggregation_job

configure_logging()
logger = get_logger(__name__)

RUN_INTERVAL_HOURS = 1


def _run_once() -> None:
    client = get_client()
    summary = run_aggregation_job(client)
    logger.info(
        "Aggregation run complete: %d advertiser(s) processed in %.2fs (%s)",
        summary.advertisers_processed,
        summary.duration_seconds,
        summary.advertiser_ids,
    )


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _run_once,
        trigger=IntervalTrigger(hours=RUN_INTERVAL_HOURS),
        id="ad_spend_aggregation",
        next_run_time=datetime.now(timezone.utc),  # run once immediately, then every interval
        misfire_grace_time=300,  # tolerate up to 5 min delay before treating a run as missed
        coalesce=True,  # if several runs were missed, catch up with ONE run, not several
        max_instances=1,  # never let two runs overlap if one runs long
    )

    logger.info("Aggregation worker starting — runs every %d hour(s)", RUN_INTERVAL_HOURS)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Aggregation worker shutting down")


if __name__ == "__main__":
    main()
