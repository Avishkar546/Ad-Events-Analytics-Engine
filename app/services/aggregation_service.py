"""
The core correctness logic of the whole project — the v3 pattern from the
Zepto article: dedup, bucket by event time (not arrival time), and
OVERWRITE (never increment) the affected windows, scoped per advertiser.

Two deliberate design choices, both explained in the implementation plan
and worth being able to defend in an interview:

1. Per-advertiser loop, not one query across all advertisers. Keeps
   compute/memory proportional to one advertiser's data, not total
   platform volume — this is the fix for the bottleneck the article hit
   at scale.

2. LOOKBACK_HOURS controls how far back we re-scan on every run. A late
   event arriving 3 hours after it happened will still get correctly
   bucketed as long as it arrives within this window. Events later than
   this are simply missed — a real tradeoff, not a hidden one.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.db.migrations_runner import ClickHouseClientProtocol

LOOKBACK_HOURS = 4
ACTIVE_WINDOW_HOURS = 1


def get_active_advertisers(
    client: ClickHouseClientProtocol, active_window_hours: int = ACTIVE_WINDOW_HOURS
) -> list[int]:
    """
    Advertisers with at least one event ingested in the last N hours.
    Scoping to "active" advertisers, not "all advertisers ever", is what
    keeps each run's cost proportional to current traffic instead of
    growing forever as the platform accumulates history.
    """
    result = client.query(f"""
        SELECT DISTINCT advertiser_id
        FROM ad_events_raw
        WHERE ingested_at >= now() - INTERVAL {active_window_hours} HOUR
    """)
    return [row[0] for row in result.result_rows]


def aggregate_advertiser(
    client: ClickHouseClientProtocol, advertiser_id: int, lookback_hours: int = LOOKBACK_HOURS
) -> None:
    """
    Recomputes and OVERWRITES every 5-minute window touched by this
    advertiser's events in the last `lookback_hours`. Reads from
    ad_events_deduped (not the raw table) so duplicate deliveries never
    get counted twice, and buckets by event_timestamp (not ingested_at)
    so late events land in the window they actually belong to.
    """
    client.command(f"""
        INSERT INTO ad_spend_5min
            (window_start, advertiser_id, campaign_id, category, device, impressions, clicks, spend)
        SELECT
            toStartOfFiveMinute(event_timestamp) AS window_start,
            advertiser_id,
            campaign_id,
            category,
            device,
            countIf(event_type = 'impression') AS impressions,
            countIf(event_type = 'click') AS clicks,
            sum(cost) AS spend
        FROM ad_events_deduped
        WHERE advertiser_id = {advertiser_id}
          AND event_timestamp >= now() - INTERVAL {lookback_hours} HOUR
        GROUP BY window_start, advertiser_id, campaign_id, category, device
    """)


@dataclass
class AggregationRunSummary:
    advertisers_processed: int = 0
    advertiser_ids: list[int] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.started_at is None or self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()


def run_aggregation_job(client: ClickHouseClientProtocol) -> AggregationRunSummary:
    summary = AggregationRunSummary(started_at=datetime.now(timezone.utc))

    advertiser_ids = get_active_advertisers(client)
    for advertiser_id in advertiser_ids:
        aggregate_advertiser(client, advertiser_id)

    summary.advertiser_ids = advertiser_ids
    summary.advertisers_processed = len(advertiser_ids)
    summary.finished_at = datetime.now(timezone.utc)
    return summary
