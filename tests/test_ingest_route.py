import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _valid_payload(**overrides) -> dict:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "click",
        "advertiser_id": 1,
        "campaign_id": 1,
        "category": "grocery",
        "device": "mobile",
        "cost": "2.5000",
        "event_timestamp": "2026-08-05T10:00:00Z",
    }
    payload.update(overrides)
    return payload


@patch("app.api.routes.ingest.insert_event")
@patch("app.api.routes.ingest.get_client")
def test_ingest_valid_event_returns_201(mock_get_client, mock_insert_event):
    payload = _valid_payload()
    response = client.post("/events/ingest", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "accepted"
    mock_insert_event.assert_called_once()


def test_ingest_rejects_malformed_event():
    payload = _valid_payload(advertiser_id=-1)  # violates gt=0 constraint
    response = client.post("/events/ingest", json=payload)

    assert response.status_code == 422  # FastAPI validation error, request never reaches ClickHouse


def test_ingest_rejects_unknown_event_type():
    payload = _valid_payload(event_type="not_a_real_type")
    response = client.post("/events/ingest", json=payload)

    assert response.status_code == 422
