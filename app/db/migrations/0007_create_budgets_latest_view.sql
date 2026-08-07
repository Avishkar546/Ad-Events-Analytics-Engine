-- Same read-time dedup pattern as ad_events_deduped (0002) and
-- ad_spend_5min_latest (0005) — never read advertiser_budgets directly.
CREATE VIEW IF NOT EXISTS advertiser_budgets_latest AS
SELECT
    advertiser_id,
    argMax(monthly_budget, updated_at) AS monthly_budget
FROM advertiser_budgets
GROUP BY advertiser_id;
