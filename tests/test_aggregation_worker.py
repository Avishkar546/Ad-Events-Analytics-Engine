"""
BlockingScheduler blocks the calling thread by design, so we can't test
main() directly in a pytest run. Instead this proves the SAME trigger
configuration (immediate first run via next_run_time=now, then interval)
actually fires, using BackgroundScheduler for the test only — production
code (app/workers/aggregation_job.py) still uses BlockingScheduler, which
is the correct choice for a standalone worker process/container.
"""
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


def test_job_with_immediate_next_run_time_fires_right_away():
    mock_job = MagicMock()

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        mock_job,
        trigger=IntervalTrigger(hours=1),
        id="test_job",
        next_run_time=datetime.now(timezone.utc),
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    time.sleep(0.5)  # give the scheduler's thread a moment to fire the immediate run
    scheduler.shutdown(wait=False)

    mock_job.assert_called_once()
