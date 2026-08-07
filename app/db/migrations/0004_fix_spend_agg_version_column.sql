-- Fixes a schema bug from 0003: the table was created with
-- ReplacingMergeTree(window_start), using window_start as the version
-- column. That's wrong — the aggregation job (v0.5) makes itself idempotent
-- by re-inserting a row for the SAME window_start every time it reruns,
-- but window_start never changes between runs, so ReplacingMergeTree had
-- no way to tell an old row from a new one.
--
-- Fix: add updated_at, a column that changes on every single insert, and
-- use THAT as the version column instead. This is the general rule for
-- ReplacingMergeTree: the version column must change on every write, never
-- be part of the logical key you're deduplicating on.
--
-- Safe to DROP + recreate here because nothing has written real data to
-- this table yet. Once real data exists, schema fixes like this require
-- add-column + backfill + engine swap via a new table, never a drop.
DROP TABLE IF EXISTS ad_spend_5min;

CREATE TABLE ad_spend_5min
(
    window_start   DateTime,
    advertiser_id  UInt32,
    campaign_id    UInt32,
    category       LowCardinality(String),
    device         LowCardinality(String),
    impressions    UInt64,
    clicks         UInt64,
    spend          Decimal(12, 4),
    updated_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toDate(window_start)
ORDER BY (advertiser_id, campaign_id, window_start);