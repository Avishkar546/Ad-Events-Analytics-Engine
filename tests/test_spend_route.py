from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.routes.spend.query_spend")
@patch("app.api.routes.spend.get_client")
def test_get_spend_rejects_invalid_group_by(mock_get_client, mock_query_spend):
    response = client.get("/advertisers/1/spend?group_by=not_a_real_field")
    assert response.status_code == 422
    mock_query_spend.assert_not_called()


@patch("app.api.routes.spend.query_spend")
@patch("app.api.routes.spend.get_client")
def test_get_spend_valid_request(mock_get_client, mock_query_spend):
    from datetime import datetime, timezone

    mock_query_spend.return_value = (
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
        [{"device": "mobile", "impressions": 1, "clicks": 1, "spend": "2.5000"}],
    )
    response = client.get("/advertisers/1/spend?group_by=device")
    assert response.status_code == 200
    assert response.json()["rows"][0]["device"] == "mobile"


@patch("app.api.routes.spend.get_budget")
@patch("app.api.routes.spend.query_total_spend")
@patch("app.api.routes.spend.get_client")
def test_budget_status_with_no_budget_set(mock_get_client, mock_total_spend, mock_get_budget):
    from decimal import Decimal

    mock_get_budget.return_value = None
    mock_total_spend.return_value = Decimal("50.0000")

    response = client.get("/advertisers/1/budget-status")
    body = response.json()
    assert response.status_code == 200
    assert body["monthly_budget"] is None
    assert body["remaining"] is None
    assert body["over_budget"] is None


@patch("app.api.routes.spend.set_budget")
@patch("app.api.routes.spend.get_client")
def test_set_budget_rejects_negative(mock_get_client, mock_set_budget):
    response = client.post("/advertisers/1/budget", json={"monthly_budget": "-5"})
    assert response.status_code == 422
    mock_set_budget.assert_not_called()
