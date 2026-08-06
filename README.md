# Ad Events Analytics Engine

Duplicate- and late-event-safe ad analytics pipeline, inspired by Zepto's
"A Billion Events a Day" ads analytics architecture. Full design docs in
`docs/ad-analytics-prd-techspec.md` and `docs/ad-analytics-implementation-plan.md`.

**Status: v0.5 — the aggregation worker. This is the core correctness
claim of the whole project.** `app/workers/aggregation_job.py` runs
`app/services/aggregation_service.py` hourly via APScheduler: for every
advertiser with recent activity, it dedupes their events, buckets them by
*event* time (not arrival time), and overwrites the affected windows in
`ad_spend_5min`. Proven correct in `tests/test_aggregation_service.py`
against real ClickHouse SQL — duplicates don't get double-counted, late
events land in their true historical window, and reruns don't double totals.

**Bug fixed this version:** `ad_spend_5min`'s original engine
(`ReplacingMergeTree(window_start)`) couldn't actually dedupe reruns —
see migration `0004` for why, and `ad_spend_5min_latest` (migration `0005`)
for the read-time fix, same pattern as `ad_events_deduped`.

## Run the worker

```bash
docker compose -f docker/docker-compose.yml up --build -d
docker compose -f docker/docker-compose.yml exec api python -m app.db.run_migrations
# worker starts automatically as its own service and runs immediately, then hourly
docker compose -f docker/docker-compose.yml logs -f worker
```

To see it do real work: generate some traffic (v0.4), then check the logs
for `Aggregation run complete: N advertiser(s) processed`, then query
ClickHouse directly:

```sql
SELECT advertiser_id, sum(spend) FROM ad_spend_5min_latest GROUP BY advertiser_id;
```

## Generate traffic against your running stack

Requires `requirements-dev.txt` installed locally (the generator is a
dev/demo tool — it's not part of the API's Docker image).

```bash
pip install -r requirements-dev.txt
python -m app.generator.event_simulator \
  --url http://localhost:8000/events/ingest \
  --count 200 --duplicate-rate 0.1 --late-rate 0.2
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
Next up: **v0.6 — the query API**, reading only from `ad_spend_5min_latest`.
