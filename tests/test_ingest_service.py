import shutil
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from chdb import session

from app.db.migrations_runner import run_migrations
from app.models.event import AdEvent, Device, EventType
from app.services.ingest_service import insert_event
from tests.chdb_test_client import ChdbTestClient

MIGRATIONS_DIR = Path(__file__).parent.parent / "app" / "db" / "migrations"


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


def _sample_event(**overrides) -> AdEvent:
    defaults = dict(
        event_id=uuid.uuid4(),
        event_type=EventType.click,
        advertiser_id=1,
        campaign_id=1,
        category="grocery",
        device=Device.mobile,
        cost=Decimal("2.5000"),
        event_timestamp=datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AdEvent(**defaults)


def test_inserted_event_is_readable_back(chdb_client):
    event = _sample_event()
    insert_event(chdb_client, event)

    result = chdb_client.query(
        f"SELECT advertiser_id, category FROM ad_events_raw WHERE event_id = '{event.event_id}'"
    )
    assert result.result_rows == [[event.advertiser_id, event.category]]


def test_duplicate_event_id_produces_two_raw_rows(chdb_client):
    # Ingest layer does NOT dedup — that's a deliberate v0.3 boundary.
    # Dedup happens at read time (ad_events_deduped) or aggregation (v0.5).
    shared_id = uuid.uuid4()
    insert_event(chdb_client, _sample_event(event_id=shared_id))
    insert_event(chdb_client, _sample_event(event_id=shared_id))

    raw_count = chdb_client.query(
        f"SELECT count() FROM ad_events_raw WHERE event_id = '{shared_id}'"
    ).result_rows[0][0]
    assert raw_count == 2

    deduped_count = chdb_client.query(
        f"SELECT count() FROM ad_events_deduped WHERE event_id = '{shared_id}'"
    ).result_rows[0][0]
    assert deduped_count == 1  # proves the dedup VIEW still does its job on top of messy raw data
