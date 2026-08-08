from datetime import datetime, timedelta, timezone

from app.services.job_run_logger import get_recent_job_runs, log_job_run


def test_log_and_read_back_job_run(chdb_client):
    started = datetime.now(timezone.utc)
    finished = started + timedelta(seconds=2)

    log_job_run(chdb_client, "ad_spend_aggregation", started, finished, 3, "success")

    runs = get_recent_job_runs(chdb_client)
    assert len(runs) == 1
    assert runs[0]["status"] == "success"
    assert runs[0]["advertisers_processed"] == 3
    assert round(runs[0]["duration_seconds"], 1) == 2.0


def test_error_message_with_quote_is_escaped(chdb_client):
    started = datetime.now(timezone.utc)
    log_job_run(chdb_client, "job", started, started, 0, "failed", "it's broken")

    runs = get_recent_job_runs(chdb_client)
    assert runs[0]["error_message"] == "it's broken"


def test_get_recent_job_runs_orders_newest_first(chdb_client):
    now = datetime.now(timezone.utc)
    log_job_run(chdb_client, "job", now - timedelta(hours=2), now - timedelta(hours=2), 1, "success")
    log_job_run(chdb_client, "job", now, now, 2, "success")

    runs = get_recent_job_runs(chdb_client)
    assert runs[0]["advertisers_processed"] == 2  # most recent first
