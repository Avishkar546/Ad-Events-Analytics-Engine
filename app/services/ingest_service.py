"""
Handles writing a validated AdEvent into ad_events_raw. Deliberately thin —
no dedup, no aggregation, no business logic here. This layer's only job is
"get the event into raw storage, with a server-assigned ingested_at."

Known limitation, on purpose for now: one row per insert() call. This is
fine for v0.3 (and for demoing correctness with the event generator in
v0.4), but a real high-throughput ingest path would batch inserts —
ClickHouse is much happier with batched writes than single-row inserts.
That's a good v2/stretch improvement to mention if asked about scaling
this further, but out of scope for the current milestone.
"""
from datetime import datetime, timezone

from app.db.migrations_runner import ClickHouseClientProtocol
from app.models.event import AdEvent

RAW_EVENTS_TABLE = "ad_events_raw"

COLUMN_NAMES = [
    "event_id",
    "event_type",
    "advertiser_id",
    "campaign_id",
    "category",
    "device",
    "cost",
    "event_timestamp",
    "ingested_at",
]


def insert_event(client: ClickHouseClientProtocol, event: AdEvent) -> None:
    ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)

    row = [
        str(event.event_id),
        event.event_type.value,
        event.advertiser_id,
        event.campaign_id,
        event.category,
        event.device.value,
        event.cost,
        event.event_timestamp.replace(tzinfo=None),
        ingested_at,
    ]

    client.insert(RAW_EVENTS_TABLE, [row], column_names=COLUMN_NAMES)
