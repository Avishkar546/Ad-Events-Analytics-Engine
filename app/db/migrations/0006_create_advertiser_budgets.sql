-- Stores each advertiser's monthly budget. A separate small table rather
-- than a column bolted onto an events/spend table, since budgets change
-- independently of traffic and are set by a completely different actor
-- (an account manager / advertiser self-serve UI, not the event pipeline).
--
-- ENGINE = ReplacingMergeTree(updated_at): applying the lesson from
-- migration 0004 correctly from the start this time — updated_at is a
-- real version column that changes on every write, so setting a new
-- budget for an advertiser (re-inserting a row) correctly supersedes the
-- old one once merged, and ad_budgets_latest (0007) guarantees correct
-- reads regardless of merge timing.
--
-- DateTime64(6) (microsecond precision), not DateTime (second precision):
-- plain DateTime means two writes in the same second get an IDENTICAL
-- version value, and argMax can't tell which was newer — a real failure
-- caught by test_setting_budget_twice_uses_latest_value, not a hypothetical.
CREATE TABLE IF NOT EXISTS advertiser_budgets
(
    advertiser_id   UInt32,
    monthly_budget  Decimal(12, 4),
    updated_at      DateTime64(6) DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (advertiser_id);
