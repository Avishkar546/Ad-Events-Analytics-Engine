from fastapi import APIRouter, Query

from app.db.clickhouse import get_client
from app.services.job_run_logger import get_recent_job_runs

router = APIRouter()


@router.get("/jobs/runs")
def list_job_runs(limit: int = Query(10, le=100)) -> list[dict]:
    client = get_client()
    return get_recent_job_runs(client, limit)
