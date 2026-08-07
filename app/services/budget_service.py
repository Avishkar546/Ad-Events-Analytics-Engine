"""
Manages advertiser_budgets. Writing a budget is an INSERT (never an
UPDATE) — same overwrite-via-new-row pattern as the aggregation job,
relying on ReplacingMergeTree + a read-time dedup view for correctness.
"""
from decimal import Decimal

from app.db.migrations_runner import ClickHouseClientProtocol


def set_budget(
    client: ClickHouseClientProtocol, advertiser_id: int, monthly_budget: Decimal
) -> None:
    client.command(f"""
        INSERT INTO advertiser_budgets (advertiser_id, monthly_budget)
        VALUES ({advertiser_id}, {monthly_budget})
    """)


def get_budget(client: ClickHouseClientProtocol, advertiser_id: int) -> Decimal | None:
    result = client.query(f"""
        SELECT monthly_budget FROM advertiser_budgets_latest WHERE advertiser_id = {advertiser_id}
    """)
    if not result.result_rows:
        return None
    return Decimal(str(result.result_rows[0][0]))
