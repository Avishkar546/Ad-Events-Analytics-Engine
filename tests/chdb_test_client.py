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
