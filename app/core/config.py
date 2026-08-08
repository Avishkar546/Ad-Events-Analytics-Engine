"""
Application configuration, sourced entirely from environment variables.
Nothing environment-specific should ever be hardcoded elsewhere in the app —
if you need a value that differs between local/staging/prod, it goes here.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "ad-analytics-engine"
    environment: str = "local"  # local | staging | production

    # ClickHouse connection — unused in v0.1 but defined now so later
    # versions don't require touching this file again.
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_db: str = "ad_analytics"
    clickhouse_secure: bool = False

@lru_cache
def get_settings() -> Settings:
    # lru_cache means settings are read from env once per process, not
    # re-parsed on every request.
    return Settings()
