from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.routes.jobs.get_recent_job_runs")
@patch("app.api.routes.jobs.get_client")
def test_list_job_runs(mock_get_client, mock_get_runs):
    mock_get_runs.return_value = [{"status": "success", "advertisers_processed": 2}]
    response = client.get("/jobs/runs")
    assert response.status_code == 200
    assert response.json()[0]["status"] == "success"
