"""
These tests run the REAL migration .sql files from app/db/migrations/
against chdb (an embedded ClickHouse engine) — not mocks. If a migration
has a syntax error or an engine ClickHouse doesn't support, these tests
catch it before you ever point them at Docker or a hosted instance.
"""
import shutil
import uuid
from pathlib import Path

import pytest
from chdb import session

from app.db.migrations_runner import run_migrations
from tests.chdb_test_client import ChdbTestClient

MIGRATIONS_DIR = Path(__file__).parent.parent / "app" / "db" / "migrations"


@pytest.fixture
def chdb_client():
    state_path = f"/tmp/chdb_test_{uuid.uuid4().hex}"
    sess = session.Session(state_path)
    sess.query("CREATE DATABASE IF NOT EXISTS ad_analytics")
    sess.query("USE ad_analytics")
    yield ChdbTestClient(sess)
    sess.close()
    shutil.rmtree(state_path, ignore_errors=True)


def test_all_migrations_apply_cleanly(chdb_client):
    applied = run_migrations(chdb_client, MIGRATIONS_DIR)
    assert applied == ["0001_create_raw_events", "0002_create_dedup_view", "0003_create_spend_agg"]


def test_migrations_are_idempotent(chdb_client):
    first_run = run_migrations(chdb_client, MIGRATIONS_DIR)
    assert len(first_run) == 3

    second_run = run_migrations(chdb_client, MIGRATIONS_DIR)
    assert second_run == []  # nothing pending — this is what makes rerunning safe on every deploy


def test_dedup_view_collapses_duplicate_event(chdb_client):
    run_migrations(chdb_client, MIGRATIONS_DIR)

    # Insert the SAME event_id twice with different ingested_at, simulating
    # a client retry — this is the core failure mode the whole project exists to fix.
    chdb_client.command("""
        INSERT INTO ad_events_raw VALUES
        ('11111111-1111-1111-1111-111111111111', 'click', 1, 1, 'grocery', 'mobile', 2.50, '2026-08-05 10:00:00', '2026-08-05 10:00:01'),
        ('11111111-1111-1111-1111-111111111111', 'click', 1, 1, 'grocery', 'mobile', 2.50, '2026-08-05 10:00:00', '2026-08-05 10:00:05')
    """)

    result = chdb_client.query("SELECT count() FROM ad_events_deduped")
    assert result.result_rows[0][0] == 1  # deduped view must show ONE event, not two
