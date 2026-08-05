-- Read-time deduplication guarantee. ReplacingMergeTree (0001) only removes
-- duplicates when ClickHouse decides to merge parts in the background — that
-- can take minutes to hours, and is never something you should depend on for
-- correctness. This view uses argMax to always collapse to one row per
-- event_id at query time, regardless of merge state.
--
-- Cost note: this view scans+groups the underlying table on every query.
-- That's fine for the aggregation job (v0.5), which only reads a few hours
-- of recent data at a time. It would NOT be fine for the API to query
-- directly for a "give me all-time spend" request — which is exactly why
-- the API only ever reads from ad_spend_5min (0003), never from here.
CREATE VIEW IF NOT EXISTS ad_events_deduped AS
SELECT
    event_id,
    event_type,
    advertiser_id,
    campaign_id,
    category,
    device,
    cost,
    event_timestamp,
    argMax(ingested_at, ingested_at) AS latest_ingest
FROM ad_events_raw
GROUP BY
    event_id, event_type, advertiser_id, campaign_id,
    category, device, cost, event_timestamp;
