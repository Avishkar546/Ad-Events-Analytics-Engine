"""
Thin wrapper around the ClickHouse client. Every other module talks to
ClickHouse through get_client() — nothing else should import
clickhouse_connect directly, so if we ever swap client libraries, this is
the only file that changes.
"""
import clickhouse_connect

from app.core.config import get_settings


def get_client():
    settings = get_settings()
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
        secure=settings.clickhouse_secure,
    )
