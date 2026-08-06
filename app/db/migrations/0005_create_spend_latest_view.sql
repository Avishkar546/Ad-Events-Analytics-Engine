-- Same reasoning as ad_events_deduped (0002): ReplacingMergeTree only
-- collapses duplicate rows during background merges, which is never
-- something to depend on for correctness. If the aggregation job reruns
-- for a window that already has a row, both rows exist in storage until
-- ClickHouse gets around to merging — this view guarantees callers always
-- see only the latest version, regardless of merge timing.
--
-- This is the view v0.6's query API will read from — never ad_spend_5min directly.
CREATE VIEW IF NOT EXISTS ad_spend_5min_latest AS
SELECT
    window_start,
    advertiser_id,
    campaign_id,
    category,
    device,
    argMax(impressions, updated_at) AS impressions,
    argMax(clicks, updated_at) AS clicks,
    argMax(spend, updated_at) AS spend
FROM ad_spend_5min
GROUP BY window_start, advertiser_id, campaign_id, category, device;
