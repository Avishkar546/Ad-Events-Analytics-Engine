"""
Migration runner for ClickHouse.

Why this exists instead of Alembic: Alembic assumes transactional DDL and a
mature SQLAlchemy dialect, neither of which ClickHouse has. The idiomatic
ClickHouse pattern is simpler and is what this implements: plain numbered
.sql files, applied in order, tracked in a table so re-running is safe.

Design note: run_migrations() takes a `client` object rather than importing
app.db.clickhouse directly. That's deliberate — it means we can test the
runner's logic (ordering, idempotency, tracking) against any object that
implements .command() and .query(), including a fast in-process ClickHouse
engine in tests, without needing a real server running. Production code
just passes the real client from app.db.clickhouse.get_client().
"""
from pathlib import Path
from typing import Protocol


class ClickHouseClientProtocol(Protocol):
    def command(self, sql: str) -> None: ...
    def query(self, sql: str): ...
    def insert(self, table: str, data: list, column_names: list[str]) -> None: ...


MIGRATIONS_TABLE = "schema_migrations"

MIGRATIONS_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE}
(
    version    String,
    applied_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY version
"""


def _applied_versions(client: ClickHouseClientProtocol) -> set[str]:
    result = client.query(f"SELECT version FROM {MIGRATIONS_TABLE}")
    return {row[0] for row in result.result_rows}


def _pending_migrations(migrations_dir: Path, applied: set[str]) -> list[Path]:
    all_files = sorted(migrations_dir.glob("*.sql"))
    return [f for f in all_files if f.stem not in applied]


def _split_statements(sql: str) -> list[str]:
    """
    ClickHouse's HTTP interface (what clickhouse-connect uses) rejects
    multiple semicolon-separated statements in a single query — unlike
    chdb, which silently allows it. Splitting here means each migration
    file can contain more than one statement (e.g. DROP + CREATE) without
    every migration author needing to remember this constraint.

    Strips `--` comment lines BEFORE splitting on ';' — otherwise an
    ordinary semicolon in English prose inside a comment (e.g. "note: X;
    also Y") gets mistaken for a statement terminator. This is a real bug
    that was caught in this project: see git history for the fix and the
    migration file that triggered it.
    """
    without_comments = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    statements = [s.strip() for s in without_comments.split(";")]
    return [s for s in statements if s]


def run_migrations(client: ClickHouseClientProtocol, migrations_dir: Path) -> list[str]:
    """
    Applies all pending .sql files in migrations_dir, in filename order.
    Returns the list of version names that were applied this run (empty
    list means everything was already up to date — this is what makes the
    runner safe to call every deploy, not just the first time).
    """
    client.command(MIGRATIONS_TABLE_DDL)

    applied = _applied_versions(client)
    pending = _pending_migrations(migrations_dir, applied)

    newly_applied = []
    for migration_file in pending:
        sql = migration_file.read_text()
        for statement in _split_statements(sql):
            client.command(statement)
        client.command(
            f"INSERT INTO {MIGRATIONS_TABLE} (version) VALUES ('{migration_file.stem}')"
        )
        newly_applied.append(migration_file.stem)

    return newly_applied
