-- Table swap via RENAME failed on ClickHouse Cloud's shared database
-- engine (doesn't support RENAME TABLE the way self-hosted does). No real
-- data exists in ad_spend_5min yet, so drop + recreate directly, same
-- pattern as migration 0004.
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
    updated_at     DateTime64(6) DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toDate(window_start)
ORDER BY (advertiser_id, campaign_id, window_start);