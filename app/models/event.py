"""
Pydantic schema for events coming into the system. This is intentionally
the ONLY validation layer — once an event passes this, it goes straight
into ad_events_raw as-is. Dedup and correctness happen downstream (v0.5),
not here. This endpoint's only job is "is this a well-formed event."
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    impression = "impression"
    click = "click"


class Device(str, Enum):
    mobile = "mobile"
    desktop = "desktop"


class AdEvent(BaseModel):
    event_id: UUID
    event_type: EventType
    advertiser_id: int = Field(gt=0)
    campaign_id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=100)
    device: Device
    cost: Decimal = Field(ge=0, decimal_places=4)
    event_timestamp: datetime  # when the event actually happened

    # ingested_at is deliberately NOT part of the input schema — the client
    # doesn't get to claim when we received their event. The server sets
    # this itself, at the point of insert. See ingest_service.py.
