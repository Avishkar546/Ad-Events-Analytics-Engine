"""
Shared fixtures for tests that need a real (embedded) ClickHouse engine.
Centralized here instead of duplicated per test file — pytest auto-discovers
fixtures in conftest.py, no import needed in the test files themselves.

Two fixtures, deliberately different:
  - chdb_raw_client: a bare embedded instance, no migrations applied.
    Used by test_migrations.py, which is specifically testing the
    migration runner itself — it needs to start from nothing.
  - chdb_client: a pre-migrated instance (migrations already applied
    during setup). Used by everything else, which wants to start from a
    ready schema without re-running migrations in every single test.

Both guarantee sess.close() via try/finally. chdb allows only ONE embedded
server per process — if setup fails partway through (e.g. a broken
migration) without closing its session, every subsequent test's fixture
fails with "EmbeddedServer already initialized with different path", which
looks like a second bug but is really just the first one's session never
having been released. The try/finally is what prevents that cascade.
"""
import shutil
import uuid
from pathlib import Path

import pytest
from chdb import session

from app.db.migrations_runner import run_migrations
from tests.chdb_test_client import ChdbTestClient

MIGRATIONS_DIR = Path(__file__).parent.parent / "app" / "db" / "migrations"


def _new_session():
    state_path = f"/tmp/chdb_test_{uuid.uuid4().hex}"
    sess = session.Session(state_path)
    sess.query("CREATE DATABASE IF NOT EXISTS ad_analytics")
    sess.query("USE ad_analytics")
    return sess, state_path


@pytest.fixture
def chdb_raw_client():
    sess, state_path = _new_session()
    try:
        yield ChdbTestClient(sess)
    finally:
        sess.close()
        shutil.rmtree(state_path, ignore_errors=True)


@pytest.fixture
def chdb_client():
    sess, state_path = _new_session()
    try:
        client = ChdbTestClient(sess)
        run_migrations(client, MIGRATIONS_DIR)
        yield client
    finally:
        sess.close()
        shutil.rmtree(state_path, ignore_errors=True)
