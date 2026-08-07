-- ClickHouse forbids ALTERing a ReplacingMergeTree version column's type
-- directly (ALTER_OF_COLUMN_IS_FORBIDDEN), so this uses the real
-- production pattern: new table + copy + swap, not a drop.
CREATE TABLE ad_spend_5min_v2
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

INSERT INTO ad_spend_5min_v2
SELECT window_start, advertiser_id, campaign_id, category, device, impressions, clicks, spend, updated_at
FROM ad_spend_5min;

RENAME TABLE ad_spend_5min TO ad_spend_5min_old, ad_spend_5min_v2 TO ad_spend_5min;

DROP TABLE ad_spend_5min_old;
