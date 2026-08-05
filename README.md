# Ad Events Analytics Engine

Duplicate- and late-event-safe ad analytics pipeline, inspired by Zepto's
"A Billion Events a Day" ads analytics architecture. Full design docs in
`docs/ad-analytics-prd-techspec.md` and `docs/ad-analytics-implementation-plan.md`.

**Status: v0.2 — ClickHouse schema in place, as version-controlled migrations.**
Real tables now exist: `ad_events_raw` (messy, allows duplicates/late events),
`ad_events_deduped` (a view guaranteeing read-time dedup), and `ad_spend_5min`
(the clean table the API will read from starting v0.6). No ingest/query
endpoints yet — that's v0.3 and v0.6.

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
Next up: **v0.3 — ingest endpoint.**
