"""
Synthetic ad-event traffic generator. Sends REAL HTTP requests to a running
ingest endpoint, producing traffic with configurable duplicate and
late-arrival rates — the two failure modes the whole project exists to
handle correctly.

This is a dev/demo tool, not part of the production API surface: app/main.py
never imports this module, so it doesn't need to ship in the API's Docker
image. Run it from your local machine (with requirements-dev.txt installed)
pointed at wherever the API is running:

    python -m app.generator.event_simulator \
        --url http://localhost:8000/events/ingest \
        --count 200 --duplicate-rate 0.1 --late-rate 0.2

Design note: this module builds the FULL list of ground-truth counts
(logical events, duplicates, late events) BEFORE sending a single request.
That's deliberate — it means the summary it prints at the end is not "what
I think I sent," it's "what I decided to send," which is what makes it
possible to independently verify the server's behavior against a known
answer (see the ClickHouse queries printed in the summary).
"""
import argparse
import asyncio
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

DEFAULT_URL = "http://localhost:8000/events/ingest"

ADVERTISER_IDS = list(range(1, 6))
CAMPAIGN_IDS_PER_ADVERTISER = 3
CATEGORIES = ["grocery", "electronics", "fashion", "pharmacy", "home"]
DEVICES = ["mobile", "desktop"]
EVENT_TYPES = ["impression", "click"]


@dataclass
class SimulatorConfig:
    url: str = DEFAULT_URL
    count: int = 100  # number of LOGICAL (unique) events to generate
    duplicate_rate: float = 0.05  # fraction of logical events sent a 2nd time
    late_rate: float = 0.10  # fraction of events given a backdated timestamp
    late_max_delay_minutes: int = 90  # how far back a "late" event's timestamp goes
    concurrency: int = 10
    events_per_second: float = 20.0  # pacing target, not a hard cap


@dataclass
class SimulationResult:
    logical_events: int = 0
    duplicate_sends: int = 0
    late_events: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    elapsed_seconds: float = 0.0


def _random_event_payload(late: bool, config: SimulatorConfig) -> dict:
    advertiser_id = random.choice(ADVERTISER_IDS)
    campaign_id = random.randint(1, CAMPAIGN_IDS_PER_ADVERTISER)

    now = datetime.now(timezone.utc)
    if late:
        delay = random.randint(1, config.late_max_delay_minutes)
        event_timestamp = now - timedelta(minutes=delay)
    else:
        event_timestamp = now

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": random.choice(EVENT_TYPES),
        "advertiser_id": advertiser_id,
        "campaign_id": campaign_id,
        "category": random.choice(CATEGORIES),
        "device": random.choice(DEVICES),
        "cost": str(Decimal(str(round(random.uniform(0.5, 5.0), 4)))),
        "event_timestamp": event_timestamp.isoformat(),
    }


def build_requests(config: SimulatorConfig) -> tuple[list[dict], SimulationResult]:
    """
    Builds the full list of HTTP payloads to send (including duplicate
    sends of the same logical event) and a SimulationResult prefilled with
    ground-truth counts — all before any network call happens.
    """
    result = SimulationResult(logical_events=config.count)
    payloads: list[dict] = []

    for _ in range(config.count):
        is_late = random.random() < config.late_rate
        payload = _random_event_payload(is_late, config)
        if is_late:
            result.late_events += 1

        payloads.append(payload)

        if random.random() < config.duplicate_rate:
            payloads.append(dict(payload))  # exact duplicate: identical event_id
            result.duplicate_sends += 1

    random.shuffle(payloads)  # duplicates shouldn't always land back-to-back
    result.total_requests = len(payloads)
    return payloads, result


async def _send_all(
    payloads: list[dict],
    config: SimulatorConfig,
    result: SimulationResult,
    client: httpx.AsyncClient,
) -> None:
    semaphore = asyncio.Semaphore(config.concurrency)
    batch_delay = (
        config.concurrency / config.events_per_second if config.events_per_second > 0 else 0
    )

    async def send_one(payload: dict) -> None:
        async with semaphore:
            try:
                response = await client.post(config.url, json=payload, timeout=10.0)
                if response.status_code == 201:
                    result.successful_requests += 1
                else:
                    result.failed_requests += 1
            except httpx.HTTPError:
                result.failed_requests += 1

    tasks = []
    for i, payload in enumerate(payloads):
        tasks.append(asyncio.create_task(send_one(payload)))
        if batch_delay and (i + 1) % config.concurrency == 0:
            await asyncio.sleep(batch_delay)

    await asyncio.gather(*tasks)


async def run_simulation(
    config: SimulatorConfig, client: httpx.AsyncClient | None = None
) -> SimulationResult:
    payloads, result = build_requests(config)

    start = time.monotonic()
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    try:
        await _send_all(payloads, config, result, client)
    finally:
        if owns_client:
            await client.aclose()
    result.elapsed_seconds = time.monotonic() - start

    return result


def _print_summary(result: SimulationResult) -> None:
    print("\n--- Simulation summary ---")
    print(f"Logical (unique) events generated : {result.logical_events}")
    print(f"Late-arriving events              : {result.late_events}")
    print(f"Duplicate sends                    : {result.duplicate_sends}")
    print(f"Total HTTP requests sent           : {result.total_requests}")
    print(f"Successful (201)                   : {result.successful_requests}")
    print(f"Failed                             : {result.failed_requests}")
    print(f"Elapsed                            : {result.elapsed_seconds:.2f}s")
    print("\nVerify independently against ClickHouse:")
    print("  SELECT count() FROM ad_events_raw;")
    print("    -- should ~= total requests sent (successful ones)")
    print("  SELECT count(DISTINCT event_id) FROM ad_events_raw;")
    print("    -- should ~= logical events generated")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ad-event traffic")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--count", type=int, default=100, help="number of unique logical events")
    parser.add_argument("--duplicate-rate", type=float, default=0.05)
    parser.add_argument("--late-rate", type=float, default=0.10)
    parser.add_argument("--late-max-delay-minutes", type=int, default=90)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--events-per-second", type=float, default=20.0)
    args = parser.parse_args()

    config = SimulatorConfig(
        url=args.url,
        count=args.count,
        duplicate_rate=args.duplicate_rate,
        late_rate=args.late_rate,
        late_max_delay_minutes=args.late_max_delay_minutes,
        concurrency=args.concurrency,
        events_per_second=args.events_per_second,
    )

    result = asyncio.run(run_simulation(config))
    _print_summary(result)


if __name__ == "__main__":
    main()
