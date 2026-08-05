-- Clean, pre-aggregated spend, bucketed into 5-minute windows keyed by
-- event_timestamp (not ingested_at) — this is what makes late events land
-- in the correct historical window instead of "today's" window.
--
-- ENGINE = ReplacingMergeTree(window_start): the aggregation job (v0.5)
-- OVERWRITES a window's totals by inserting a new row for the same key —
-- it never increments in place. ReplacingMergeTree lets us do this safely:
-- re-running the job for a window that already has data just produces a
-- newer version of that row, which eventually replaces the old one.
--
-- ORDER BY (advertiser_id, campaign_id, window_start): the API's most common
-- query shape is "this advertiser's spend, optionally by campaign, over a
-- time range" — this key makes that a sorted-range scan, not a full scan.
CREATE TABLE IF NOT EXISTS ad_spend_5min
(
    window_start   DateTime,
    advertiser_id  UInt32,
    campaign_id    UInt32,
    category       LowCardinality(String),
    device         LowCardinality(String),
    impressions    UInt64,
    clicks         UInt64,
    spend          Decimal(12, 4)
)
ENGINE = ReplacingMergeTree(window_start)
PARTITION BY toDate(window_start)
ORDER BY (advertiser_id, campaign_id, window_start);
