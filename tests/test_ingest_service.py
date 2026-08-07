import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.models.event import AdEvent, Device, EventType
from app.services.ingest_service import insert_event


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
