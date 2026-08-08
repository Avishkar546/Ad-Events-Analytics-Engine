import uuid
from datetime import datetime

from app.db.migrations_runner import ClickHouseClientProtocol


def log_job_run(
    client: ClickHouseClientProtocol,
    job_name: str,
    started_at: datetime,
    finished_at: datetime,
    advertisers_processed: int,
    status: str,
    error_message: str = "",
) -> None:
    duration = (finished_at - started_at).total_seconds()
    escaped_error = error_message.replace("'", "''")
    client.command(f"""
        INSERT INTO job_runs
            (run_id, job_name, started_at, finished_at, duration_seconds,
             advertisers_processed, status, error_message)
        VALUES
            ('{uuid.uuid4()}', '{job_name}', '{started_at.strftime("%Y-%m-%d %H:%M:%S.%f")}',
             '{finished_at.strftime("%Y-%m-%d %H:%M:%S.%f")}', {duration}, {advertisers_processed},
             '{status}', '{escaped_error}')
    """)


def get_recent_job_runs(client: ClickHouseClientProtocol, limit: int = 10) -> list[dict]:
    result = client.query(f"""
        SELECT run_id, job_name, started_at, finished_at, duration_seconds,
               advertisers_processed, status, error_message
        FROM job_runs
        ORDER BY started_at DESC
        LIMIT {limit}
    """)
    columns = [
        "run_id", "job_name", "started_at", "finished_at",
        "duration_seconds", "advertisers_processed", "status", "error_message",
    ]
    return [dict(zip(columns, row, strict=True)) for row in result.result_rows]
