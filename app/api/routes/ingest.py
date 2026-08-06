"""
POST /events/ingest — accepts one ad event, validates it, writes it to
ad_events_raw. Deliberately does not check for duplicates or reject
anything based on business rules — that's not this endpoint's job (see
ingest_service.py). If it's a well-formed event, it gets stored.
"""
from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.db.clickhouse import get_client
from app.models.event import AdEvent
from app.services.ingest_service import insert_event

router = APIRouter()
logger = get_logger(__name__)


@router.post("/events/ingest", status_code=201)
def ingest_event(event: AdEvent) -> dict:
    try:
        client = get_client()
        insert_event(client, event)
    except Exception:
        logger.exception("Failed to insert event %s", event.event_id)
        raise HTTPException(status_code=502, detail="Failed to store event") from None

    return {"status": "accepted", "event_id": str(event.event_id)}
