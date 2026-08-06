# Ad Events Analytics Engine

Duplicate- and late-event-safe ad analytics pipeline, inspired by Zepto's
"A Billion Events a Day" ads analytics architecture. Full design docs in
`docs/ad-analytics-prd-techspec.md` and `docs/ad-analytics-implementation-plan.md`.

**Status: v0.3 — ingest endpoint.** `POST /events/ingest` accepts a single
ad event, validates it, and writes it to `ad_events_raw`. Deliberately does
**not** dedup at this layer — duplicates are expected to land in raw
storage; dedup happens at read time (`ad_events_deduped`) or aggregation
(v0.5). Query endpoints still don't exist — that's v0.6.

## Try it

```bash
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d '{
        "event_id": "11111111-1111-1111-1111-111111111111",
        "event_type": "click",
        "advertiser_id": 1,
        "campaign_id": 1,
        "category": "grocery",
        "device": "mobile",
        "cost": "2.5000",
        "event_timestamp": "2026-08-05T10:00:00Z"
      }'
```

Posting the exact same `event_id` twice is expected to succeed both times
— that's the point. Check `docs/` for why.

## Run locally (without Docker)

```bash
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

## Run locally (with Docker Compose — ClickHouse + API)

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build -d
# apply schema migrations against the running ClickHouse container:
docker compose -f docker/docker-compose.yml exec api python -m app.db.run_migrations
curl http://localhost:8000/health
```

## Why ClickHouse, and why not Alembic for migrations

Short version: this workload is analytical (scan millions of rows, aggregate
by column) rather than transactional (fetch one row by ID), which is exactly
what ClickHouse's column-oriented storage is built for. Alembic assumes
transactional DDL and a mature SQLAlchemy dialect — neither fits ClickHouse
well — so migrations here are plain numbered `.sql` files applied by a small
custom runner (`app/db/migrations_runner.py`), tracked in a `schema_migrations`
table so re-running is always safe. Full reasoning in `docs/`.

## Run tests

```bash
pytest tests/ -v
ruff check app/ tests/
```

Migration tests (`tests/test_migrations.py`) run the real `.sql` files
against `chdb`, an embedded ClickHouse engine — this validates the actual
schema and the dedup logic without needing Docker or a live server for CI.

## Roadmap

See `docs/ad-analytics-implementation-plan.md` for the full v0.1–v0.9 plan.
Next up: **v0.4 — event generator (synthetic traffic with duplicate/late-arrival controls).**
