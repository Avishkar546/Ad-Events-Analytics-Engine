# Ad Events Analytics Engine

Duplicate- and late-event-safe ad analytics pipeline, inspired by Zepto's
"A Billion Events a Day" ads analytics architecture. Full design docs in
`docs/ad-analytics-prd-techspec.md` and `docs/ad-analytics-implementation-plan.md`.

**Status: v0.4 — event generator.** `app/generator/event_simulator.py`
produces synthetic traffic and sends it as REAL HTTP requests to a running
`/events/ingest` endpoint, with independently-controllable duplicate and
late-arrival rates. This is what v0.5's aggregation job will be tested
against.

## Generate traffic against your running stack

Requires `requirements-dev.txt` installed locally (the generator is a
dev/demo tool — it's not part of the API's Docker image).

```bash
pip install -r requirements-dev.txt
python -m app.generator.event_simulator \
  --url http://localhost:8000/events/ingest \
  --count 200 --duplicate-rate 0.1 --late-rate 0.2
```

It prints a summary with ground-truth counts (how many logical events, how
many were sent as duplicates, how many were backdated) and the exact
ClickHouse queries to run to verify the server's behavior matches:

```sql
SELECT count() FROM ad_events_raw;                  -- ≈ total requests sent
SELECT count(DISTINCT event_id) FROM ad_events_raw;  -- ≈ logical events generated
```

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
Next up: **v0.5 — the aggregation worker.** This is the core correctness
claim of the whole project: run the generator with known duplicate/late
rates, run the aggregation job, and prove `ad_spend_5min` matches
hand-calculated expected totals.
