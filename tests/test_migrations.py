"""
These tests run the REAL migration .sql files from app/db/migrations/
against chdb (an embedded ClickHouse engine) — not mocks. If a migration
has a syntax error or an engine ClickHouse doesn't support, these tests
catch it before you ever point them at Docker or a hosted instance.
"""
from app.db.migrations_runner import run_migrations
from tests.conftest import MIGRATIONS_DIR


def test_all_migrations_apply_cleanly(chdb_raw_client):
    applied = run_migrations(chdb_raw_client, MIGRATIONS_DIR)
    assert applied == [
        "0001_create_raw_events",
        "0002_create_dedup_view",
        "0003_create_spend_agg",
        "0004_fix_spend_agg_version_column",
        "0005_create_spend_latest_view",
    ]


def test_migrations_are_idempotent(chdb_raw_client):
    first_run = run_migrations(chdb_raw_client, MIGRATIONS_DIR)
    assert len(first_run) == 5

    second_run = run_migrations(chdb_raw_client, MIGRATIONS_DIR)
    assert second_run == []  # nothing pending — this is what makes rerunning safe on every deploy


def test_dedup_view_collapses_duplicate_event(chdb_raw_client):
    run_migrations(chdb_raw_client, MIGRATIONS_DIR)

    # Insert the SAME event_id twice with different ingested_at, simulating
    # a client retry — this is the core failure mode the whole project exists to fix.
    chdb_raw_client.command("""
        INSERT INTO ad_events_raw VALUES
        ('11111111-1111-1111-1111-111111111111', 'click', 1, 1, 'grocery', 'mobile', 2.50, '2026-08-05 10:00:00', '2026-08-05 10:00:01'),
        ('11111111-1111-1111-1111-111111111111', 'click', 1, 1, 'grocery', 'mobile', 2.50, '2026-08-05 10:00:00', '2026-08-05 10:00:05')
    """)

    result = chdb_raw_client.query("SELECT count() FROM ad_events_deduped")
    assert result.result_rows[0][0] == 1  # deduped view must show ONE event, not two
