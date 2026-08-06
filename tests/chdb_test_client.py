"""
A minimal adapter exposing the same .command()/.query() shape as
clickhouse_connect's real client, backed by chdb (an embedded, in-process
ClickHouse engine). This lets tests exercise the actual migration SQL
against a real ClickHouse query engine — not a mock — without requiring
Docker or a running server. Test-only; production uses app.db.clickhouse.
"""
from dataclasses import dataclass


@dataclass
class _QueryResult:
    result_rows: list


class ChdbTestClient:
    def __init__(self, session):
        self._session = session

    def command(self, sql: str) -> None:
        self._session.query(sql)

    def query(self, sql: str) -> _QueryResult:
        result = self._session.query(sql, "JSONCompact")
        import json

        parsed = json.loads(result.bytes())
        return _QueryResult(result_rows=parsed.get("data", []))

    def insert(self, table: str, data: list, column_names: list[str]) -> None:
        # Mimics clickhouse_connect's insert() signature so ingest_service.py
        # can be tested unmodified against chdb instead of a live server.
        columns = ", ".join(column_names)
        value_rows = []
        for row in data:
            formatted = ", ".join(_sql_literal(v) for v in row)
            value_rows.append(f"({formatted})")
        sql = f"INSERT INTO {table} ({columns}) VALUES {', '.join(value_rows)}"
        self._session.query(sql)


def _sql_literal(value) -> str:
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if hasattr(value, "isoformat"):  # datetime
        return f"'{value.isoformat(sep=' ')}'"
    return str(value)
