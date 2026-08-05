-- Raw event storage. This table is intentionally "messy" — duplicates and
-- late-arriving events are allowed in here. We never query it directly from
-- the API; we only ever go through ad_events_deduped (0002) or the
-- pre-aggregated ad_spend_5min (0003).
--
-- ENGINE choice: ReplacingMergeTree(ingested_at) deduplicates rows with the
-- same ORDER BY key during background merges, keeping the row with the
-- highest ingested_at. This is a storage-level optimization, NOT a
-- guarantee — merges happen on ClickHouse's own schedule, which is why we
-- still need ad_events_deduped as a read-time safety net (see 0002).
--
-- PARTITION BY toDate(event_timestamp): partitions are ClickHouse's unit of
-- data management (dropping old data, parallelizing merges). Partitioning
-- by the day the event happened — not the day it arrived — keeps a late
-- event physically stored with the day it belongs to, not the day it showed up.
--
-- ORDER BY (advertiser_id, campaign_id, event_id): this is the single most
-- consequential schema decision in the whole project. ClickHouse physically
-- sorts data on disk by this key. Because almost every query we run filters
-- by advertiser_id (and often campaign_id), ClickHouse can skip straight to
-- the relevant data blocks instead of scanning the whole partition. This is
-- also what keeps the per-advertiser aggregation job (v0.5) cheap.
CREATE TABLE IF NOT EXISTS ad_events_raw
(
    event_id        UUID,
    event_type      LowCardinality(String),
    advertiser_id   UInt32,
    campaign_id     UInt32,
    category        LowCardinality(String),
    device          LowCardinality(String),
    cost            Decimal(10, 4),
    event_timestamp DateTime,
    ingested_at     DateTime
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toDate(event_timestamp)
ORDER BY (advertiser_id, campaign_id, event_id);
