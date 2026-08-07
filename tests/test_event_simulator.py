import asyncio
import random
from unittest.mock import patch

import httpx

from app.generator.event_simulator import SimulatorConfig, build_requests, run_simulation
from app.main import app


def test_build_requests_respects_configured_rates():
    random.seed(42)
    config = SimulatorConfig(count=500, duplicate_rate=0.2, late_rate=0.3)
    payloads, result = build_requests(config)

    assert result.logical_events == 500
    assert result.total_requests == 500 + result.duplicate_sends
    assert len(payloads) == result.total_requests

    # Statistical, not exact — random.random() < rate over 500 trials.
    # Wide-ish tolerance keeps this test stable across seeds/runs.
    assert abs(result.duplicate_sends - 100) < 40  # expected ~20% of 500
    assert abs(result.late_events - 150) < 50  # expected ~30% of 500


def test_duplicate_payloads_share_event_id_and_other_fields():
    random.seed(1)
    config = SimulatorConfig(count=50, duplicate_rate=1.0, late_rate=0.0)  # force every event duplicated
    payloads, result = build_requests(config)

    assert result.duplicate_sends == 50
    assert len(payloads) == 100

    event_ids = [p["event_id"] for p in payloads]
    # every event_id should appear exactly twice
    for eid in set(event_ids):
        assert event_ids.count(eid) == 2


@patch("app.api.routes.ingest.insert_event")
@patch("app.api.routes.ingest.get_client")
def test_generator_sends_real_requests_through_the_actual_api(mock_get_client, mock_insert_event):
    """
    Sends generated payloads through the REAL FastAPI app (in-process via
    ASGI transport, no network needed) with only insert_event mocked out
    (we don't have a live ClickHouse in this test). This proves every
    payload the generator produces actually satisfies the real AdEvent
    validation — not a hand-picked example, but whatever the generator
    happens to produce, including duplicates and late timestamps.
    """
    random.seed(7)

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            config = SimulatorConfig(
                url="http://test/events/ingest",
                count=20,
                duplicate_rate=0.25,
                late_rate=0.25,
                concurrency=5,
                events_per_second=10_000,  # don't throttle in tests
            )
            return await run_simulation(config, client=client)

    result = asyncio.run(_run())

    assert result.failed_requests == 0
    assert result.successful_requests == result.total_requests
    assert mock_insert_event.call_count == result.total_requests
