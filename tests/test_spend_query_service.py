import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.budget_service import get_budget, set_budget
from app.services.spend_query_service import query_spend, query_total_spend, validate_group_by

ADVERTISER_ID = 7


def _insert_spend_row(client, campaign_id, category, device, impressions, clicks, spend, window_start):
    client.command(f"""
        INSERT INTO ad_spend_5min
            (window_start, advertiser_id, campaign_id, category, device, impressions, clicks, spend)
        VALUES
            ('{window_start}', {ADVERTISER_ID}, {campaign_id}, '{category}', '{device}', {impressions}, {clicks}, {spend})
    """)


def test_validate_group_by_accepts_allowed_fields():
    validate_group_by(["campaign_id", "device"])  # should not raise


def test_validate_group_by_rejects_unknown_field():
    # This is the injection defense: an attacker-controlled group_by value
    # that isn't in the whitelist must be rejected BEFORE it ever reaches SQL.
    with pytest.raises(ValueError, match="Invalid group_by"):
        validate_group_by(["advertiser_id"])  # not in ALLOWED_GROUP_BY, even though it's a real column

    with pytest.raises(ValueError, match="Invalid group_by"):
        validate_group_by(["campaign_id; DROP TABLE ad_spend_5min --"])


def test_query_spend_totals_without_grouping(chdb_client):
    now = datetime.now(timezone.utc)
    window = now.strftime("%Y-%m-%d %H:%M:%S")

    _insert_spend_row(chdb_client, 1, "grocery", "mobile", 10, 2, "5.0000", window)
    _insert_spend_row(chdb_client, 2, "electronics", "desktop", 20, 3, "7.5000", window)

    from_dt, to_dt, rows = query_spend(
        chdb_client, ADVERTISER_ID, from_dt=now - timedelta(hours=1), to_dt=now + timedelta(minutes=1)
    )

    assert len(rows) == 1  # no group_by -> one aggregated row
    assert rows[0]["impressions"] == 30
    assert rows[0]["clicks"] == 5
    assert Decimal(str(rows[0]["spend"])) == Decimal("12.5000")


def test_query_spend_grouped_by_device(chdb_client):
    now = datetime.now(timezone.utc)
    window = now.strftime("%Y-%m-%d %H:%M:%S")

    _insert_spend_row(chdb_client, 1, "grocery", "mobile", 10, 2, "5.0000", window)
    _insert_spend_row(chdb_client, 2, "electronics", "desktop", 20, 3, "7.5000", window)

    _, _, rows = query_spend(
        chdb_client,
        ADVERTISER_ID,
        from_dt=now - timedelta(hours=1),
        to_dt=now + timedelta(minutes=1),
        group_by=["device"],
    )

    by_device = {row["device"]: row for row in rows}
    assert Decimal(str(by_device["mobile"]["spend"])) == Decimal("5.0000")
    assert Decimal(str(by_device["desktop"]["spend"])) == Decimal("7.5000")


def test_query_spend_excludes_rows_outside_time_range(chdb_client):
    now = datetime.now(timezone.utc)
    inside_window = now.strftime("%Y-%m-%d %H:%M:%S")
    outside_window = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

    _insert_spend_row(chdb_client, 1, "grocery", "mobile", 10, 2, "5.0000", inside_window)
    _insert_spend_row(chdb_client, 1, "grocery", "mobile", 999, 999, "999.0000", outside_window)

    _, _, rows = query_spend(
        chdb_client, ADVERTISER_ID, from_dt=now - timedelta(hours=1), to_dt=now + timedelta(minutes=1)
    )

    assert len(rows) == 1
    assert Decimal(str(rows[0]["spend"])) == Decimal("5.0000")  # the 999 row must be excluded


def test_budget_set_and_get_roundtrip(chdb_client):
    assert get_budget(chdb_client, ADVERTISER_ID) is None  # nothing set yet

    set_budget(chdb_client, ADVERTISER_ID, Decimal("1000.0000"))
    assert get_budget(chdb_client, ADVERTISER_ID) == Decimal("1000.0000")


def test_setting_budget_twice_uses_latest_value(chdb_client):
    # Same overwrite-via-reinsert pattern as the aggregation job — proves
    # the ReplacingMergeTree + view fix from 0006/0007 actually works.
    set_budget(chdb_client, ADVERTISER_ID, Decimal("1000.0000"))
    set_budget(chdb_client, ADVERTISER_ID, Decimal("1500.0000"))

    assert get_budget(chdb_client, ADVERTISER_ID) == Decimal("1500.0000")


def test_query_total_spend_sums_correctly(chdb_client):
    now = datetime.now(timezone.utc)
    window = now.strftime("%Y-%m-%d %H:%M:%S")
    _insert_spend_row(chdb_client, 1, "grocery", "mobile", 10, 2, "5.0000", window)
    _insert_spend_row(chdb_client, 2, "electronics", "desktop", 20, 3, "7.5000", window)

    total = query_total_spend(chdb_client, ADVERTISER_ID, now - timedelta(hours=1), now + timedelta(minutes=1))
    assert total == Decimal("12.5000")


def test_query_total_spend_returns_zero_when_no_data(chdb_client):
    now = datetime.now(timezone.utc)
    total = query_total_spend(chdb_client, uuid.uuid4().int % 100000, now - timedelta(hours=1), now)
    assert total == Decimal("0")
