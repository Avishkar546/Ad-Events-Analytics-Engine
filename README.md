# Ad Events Analytics Engine

Duplicate- and late-event-safe ad analytics pipeline, inspired by Zepto's
"A Billion Events a Day" ads analytics architecture. Full design docs in
`docs/ad-analytics-prd-techspec.md` and `docs/ad-analytics-implementation-plan.md`.

**Status: v0.1 — skeleton + deploy pipeline.** No real analytics logic yet —
this version exists purely to prove the app runs, tests pass in CI, and the
Docker/compose setup works, before any business logic is added.

## Run locally (without Docker)

```bash
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

## Run locally (with Docker Compose — brings up ClickHouse too, unused until v0.2)

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
curl http://localhost:8000/health
```

## Run tests

```bash
pytest tests/ -v
ruff check app/
```

## Roadmap

See `docs/ad-analytics-implementation-plan.md` for the full v0.1–v0.9 plan.
Next up: **v0.2 — ClickHouse schema as version-controlled migrations.**
