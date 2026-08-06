"""
This is the test that proves the whole project's core claim. If this
passes, the system correctly: (1) ignores a duplicate delivery of the same
event, (2) buckets a late-arriving event into the correct historical
window rather than "now", and (3) is safe to rerun without double-counting.
Runs against real ClickHouse SQL via chdb — not mocks.
"""
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from chdb import session

from app.db.migrations_runner import run_migrations
from app.services.aggregation_service import run_aggregation_job
from tests.chdb_test_client import ChdbTestClient

MIGRATIONS_DIR = Path(__file__).parent.parent / "app" / "db" / "migrations"

ADVERTISER_ID = 1
CAMPAIGN_ID = 1


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@pytest.fixture
def chdb_client():
    state_path = f"/tmp/chdb_test_{uuid.uuid4().hex}"
    sess = session.Session(state_path)
    sess.query("CREATE DATABASE IF NOT EXISTS ad_analytics")
    sess.query("USE ad_analytics")
    client = ChdbTestClient(sess)
    run_migrations(client, MIGRATIONS_DIR)
    yield client
    sess.close()
    shutil.rmtree(state_path, ignore_errors=True)


def _insert_raw_event(client, event_id, event_type, cost, event_timestamp, ingested_at):
    client.command(f"""
        INSERT INTO ad_events_raw
            (event_id, event_type, advertiser_id, campaign_id, category, device, cost, event_timestamp, ingested_at)
        VALUES
            ('{event_id}', '{event_type}', {ADVERTISER_ID}, {CAMPAIGN_ID}, 'grocery', 'mobile', {cost}, '{event_timestamp}', '{ingested_at}')
    """)


def test_aggregation_handles_duplicates_and_late_events_correctly(chdb_client):
    # Scenario, relative to the REAL current time so this test is correct
    # on any day it runs, not just today:
    #   - one impression, on time                         -> counts once
    #   - one click, on time, delivered TWICE (duplicate)  -> counts once, not twice
    #   - one click, LATE (happened 90 min ago, arrived just now) -> still counted,
    #     bucketed into its OWN (earlier) window, not "now"
    now = datetime.now(timezone.utc)
    now_str = _fmt(now)

    _insert_raw_event(chdb_client, uuid.uuid4(), "impression", "1.0000", now_str, now_str)

    click_id = uuid.uuid4()
    _insert_raw_event(chdb_client, click_id, "click", "2.5000", now_str, now_str)
    _insert_raw_event(chdb_client, click_id, "click", "2.5000", now_str, now_str)  # duplicate delivery

    late_click_id = uuid.uuid4()
    late_event_timestamp = _fmt(now - timedelta(minutes=90))  # happened 90 min before "now"
    _insert_raw_event(chdb_client, late_click_id, "click", "3.0000", late_event_timestamp, now_str)

    # Sanity check on the raw data itself: 4 rows in, only because of the duplicate
    raw_count = chdb_client.query("SELECT count() FROM ad_events_raw").result_rows[0][0]
    assert raw_count == 4

    run_aggregation_job(chdb_client)

    totals = chdb_client.query(f"""
        SELECT sum(impressions), sum(clicks), sum(spend)
        FROM ad_spend_5min_latest
        WHERE advertiser_id = {ADVERTISER_ID}
    """).result_rows[0]

    total_impressions, total_clicks, total_spend = totals
    assert total_impressions == 1
    assert total_clicks == 2  # on-time click + late click, duplicate NOT double-counted
    assert Decimal(total_spend) == Decimal("6.5000")  # 1.00 + 2.50 + 3.00 — NOT 9.00

    # The late event must land in ITS OWN window (10:30), not "now"'s window (12:00) —
    # this is the whole point of bucketing by event_timestamp instead of ingested_at.
    windows = chdb_client.query(f"""
        SELECT DISTINCT window_start FROM ad_spend_5min_latest
        WHERE advertiser_id = {ADVERTISER_ID}
        ORDER BY window_start
    """).result_rows
    assert len(windows) == 2  # one window for the 12:00 events, one for the 10:30 late event


def test_rerunning_the_job_does_not_double_count(chdb_client):
    now_str = _fmt(datetime.now(timezone.utc))
    _insert_raw_event(chdb_client, uuid.uuid4(), "click", "5.0000", now_str, now_str)

    run_aggregation_job(chdb_client)
    first_total = chdb_client.query(
        f"SELECT sum(spend) FROM ad_spend_5min_latest WHERE advertiser_id = {ADVERTISER_ID}"
    ).result_rows[0][0]

    run_aggregation_job(chdb_client)  # rerun with no new data — must overwrite, not add
    second_total = chdb_client.query(
        f"SELECT sum(spend) FROM ad_spend_5min_latest WHERE advertiser_id = {ADVERTISER_ID}"
    ).result_rows[0][0]

    assert Decimal(first_total) == Decimal("5.0000")
    assert Decimal(second_total) == Decimal("5.0000")  # NOT 10.00 — this is the idempotency guarantee


def test_advertiser_with_no_recent_events_is_not_processed(chdb_client):
    # An advertiser with events older than ACTIVE_WINDOW_HOURS shouldn't be
    # picked up at all — this is what keeps each run's cost proportional to
    # CURRENT traffic, not total platform history.
    old_ingested_at = "2020-01-01 00:00:00"
    _insert_raw_event(
        chdb_client, uuid.uuid4(), "click", "1.0000", "2020-01-01 00:00:00", old_ingested_at
    )

    summary = run_aggregation_job(chdb_client)
    assert summary.advertisers_processed == 0
    assert summary.advertiser_ids == []
