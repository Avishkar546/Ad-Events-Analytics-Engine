"""
Serves advertiser spend queries. Reads ONLY from ad_spend_5min_latest —
never ad_events_raw or ad_spend_5min directly. This is the whole payoff of
v0.5's aggregation job: queries here are always fast, over a small
pre-aggregated table, regardless of how much raw event history has piled up.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db.migrations_runner import ClickHouseClientProtocol

# Whitelist, not a suggestion: group_by values come from user-supplied query
# params. Column names can't be parameterized like values can (no "?"
# placeholder for identifiers), so the only safe way to let a caller choose
# grouping columns is to check the requested names against a fixed,
# hardcoded set before ever interpolating them into SQL.
ALLOWED_GROUP_BY = {"campaign_id", "category", "device"}

DEFAULT_LOOKBACK_HOURS = 24


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def validate_group_by(group_by: list[str]) -> None:
    invalid = set(group_by) - ALLOWED_GROUP_BY
    if invalid:
        raise ValueError(
            f"Invalid group_by field(s): {sorted(invalid)}. Allowed: {sorted(ALLOWED_GROUP_BY)}"
        )


def query_spend(
    client: ClickHouseClientProtocol,
    advertiser_id: int,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    group_by: list[str] | None = None,
) -> tuple[datetime, datetime, list[dict]]:
    """
    Returns (resolved_from, resolved_to, rows) — resolving defaults here,
    once, and handing the actual values back to the caller means the route
    layer never has to duplicate (and risk drifting from) this logic just
    to report what range was actually queried.
    """
    group_by = group_by or []
    validate_group_by(group_by)  # raises before touching the database on bad input

    to_dt = to_dt or datetime.now(timezone.utc)
    from_dt = from_dt or (to_dt - timedelta(hours=DEFAULT_LOOKBACK_HOURS))

    dimension_cols = ", ".join(group_by)
    select_dimensions = f"{dimension_cols}, " if dimension_cols else ""
    group_clause = f"GROUP BY {dimension_cols}" if dimension_cols else ""

    result = client.query(f"""
        SELECT
            {select_dimensions}
            sum(impressions) AS impressions,
            sum(clicks) AS clicks,
            sum(spend) AS spend
        FROM ad_spend_5min_latest
        WHERE advertiser_id = {advertiser_id}
          AND window_start >= '{_fmt(from_dt)}'
          AND window_start < '{_fmt(to_dt)}'
        {group_clause}
    """)

    columns = [*group_by, "impressions", "clicks", "spend"]
    rows = [dict(zip(columns, row, strict=True)) for row in result.result_rows]
    return from_dt, to_dt, rows


def query_total_spend(
    client: ClickHouseClientProtocol,
    advertiser_id: int,
    from_dt: datetime,
    to_dt: datetime,
) -> Decimal:
    """Single total, no grouping — used by budget-status."""
    result = client.query(f"""
        SELECT sum(spend)
        FROM ad_spend_5min_latest
        WHERE advertiser_id = {advertiser_id}
          AND window_start >= '{_fmt(from_dt)}'
          AND window_start < '{_fmt(to_dt)}'
    """)
    if not result.result_rows or result.result_rows[0][0] is None:
        return Decimal("0")
    return Decimal(str(result.result_rows[0][0]))
