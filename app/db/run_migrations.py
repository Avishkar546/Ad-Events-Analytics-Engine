"""
Run with: python -m app.db.run_migrations
Applies any pending migrations in app/db/migrations/ against the ClickHouse
instance configured via environment variables (see .env.example).
"""
from pathlib import Path

from app.core.logging import configure_logging, get_logger
from app.db.clickhouse import get_client
from app.db.migrations_runner import run_migrations

configure_logging()
logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def main() -> None:
    client = get_client()
    applied = run_migrations(client, MIGRATIONS_DIR)

    if applied:
        logger.info("Applied %d migration(s): %s", len(applied), ", ".join(applied))
    else:
        logger.info("No pending migrations — schema already up to date.")


if __name__ == "__main__":
    main()
