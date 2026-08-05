# Ad Events Analytics Engine — Implementation Plan

Companion to `ad-analytics-prd-techspec.md`. This document answers: how do we start, how is the repo organized, and how do we ship something deployed at every step instead of one big-bang launch.

---

## 1. Guiding principles

- **Every version (v0.1, v0.2, ...) is independently deployable and demoable.** No version should leave the system in a broken state.
- **Config over hardcoding.** Nothing environment-specific lives in code — connection strings, secrets, feature flags all come from environment variables.
- **Migrations are code, not manual SQL you ran once.** Every schema change is a numbered file, checked into git, runnable from scratch.
- **Tests before the next version starts.** Each version gets at least a couple of tests proving its core claim (e.g. "duplicates don't get double-counted") before you move on.
- **The worker and the API are separate deployable services**, even if they share code — this mirrors how it would actually run in production and is worth being able to explain.

---

## 2. Repository structure

```
ad-analytics-engine/
├── app/
│   ├── main.py                     # FastAPI app entrypoint
│   ├── api/
│   │   └── routes/
│   │       ├── health.py
│   │       ├── ingest.py
│   │       └── spend.py
│   ├── core/
│   │   ├── config.py                # pydantic Settings, reads from env
│   │   └── logging.py
│   ├── db/
│   │   ├── clickhouse.py            # connection/client setup
│   │   └── migrations/
│   │       ├── 0001_create_raw_events.sql
│   │       ├── 0002_create_dedup_view.sql
│   │       └── 0003_create_spend_agg.sql
│   ├── models/
│   │   └── event.py                 # pydantic schemas
│   ├── services/
│   │   ├── ingest_service.py
│   │   └── aggregation_service.py
│   ├── workers/
│   │   └── aggregation_job.py       # the scheduled job, runnable standalone
│   └── generator/
│       └── event_simulator.py       # synthetic traffic + dupe/late injection
├── tests/
│   ├── conftest.py
│   ├── test_ingest.py
│   └── test_aggregation.py
├── scripts/
│   ├── run_migrations.sh
│   └── run_worker.sh
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── docker-compose.yml           # ClickHouse + API + worker, one command
├── .github/workflows/ci.yml
├── .env.example
├── pyproject.toml
├── README.md
└── docs/
    └── ad-analytics-prd-techspec.md
```

Why the worker gets its own `Dockerfile.worker` even though it shares `app/` code with the API: in a real deployment these scale independently (API needs to handle request bursts, the worker just needs to run once an hour) — treating them as separate services from day one avoids a rewrite later.

---

## 3. Deployment approach

Keep it boring and free-tier-friendly — the point is to demonstrate you *can* deploy and operate this, not to run real billion-event traffic.

- **Local dev**: `docker-compose up` — spins up ClickHouse + API + worker together. This is your inner loop.
- **Hosted**: FastAPI service on Render or Fly.io (both have free/cheap tiers and are simple to wire to GitHub). ClickHouse via ClickHouse Cloud's free trial tier, or self-hosted in the same docker-compose if you deploy to a small VM instead.
- **CI/CD**: GitHub Actions — on every push to `main`: run tests → build Docker images → deploy on success. Never deploy on a failing test.
- **Secrets**: stored in the platform's secret manager (Render/Fly env vars), never committed. `.env.example` documents what's needed without real values.

---

## 4. Version-by-version plan

Each version below has a goal, a definition of done, and what you deploy/demo at the end of it.

### v0.1 — Skeleton + "hello world" deploy
**Goal:** Prove the deployment pipeline works before any real logic exists.
**Build:** FastAPI app with a single `/health` endpoint. Dockerfile. docker-compose with FastAPI + ClickHouse (empty, no schema yet). GitHub Actions running tests on push.
**Done when:** `/health` returns 200 locally *and* on the hosted deployment.
**Deploy:** Push to Render/Fly, confirm the public URL responds.

### v0.2 — Schema in place
**Goal:** ClickHouse has the real tables, version-controlled as migrations.
**Build:** `0001_create_raw_events.sql`, `0002_create_dedup_view.sql`, `0003_create_spend_agg.sql`. A `run_migrations.sh` that applies them in order.
**Done when:** running the migration script against a fresh ClickHouse instance produces all three objects, verified with a manual `SELECT`.
**Deploy:** Run migrations against the hosted ClickHouse instance.

### v0.3 — Ingest endpoint
**Goal:** Real events can be written in.
**Build:** `POST /events/ingest`, pydantic validation on the event schema, writes to `ad_events_raw`.
**Done when:** a test posts an event and confirms it's readable back from ClickHouse. A second test posts the *same* `event_id` twice and confirms the raw table has two rows (dedup hasn't happened yet — that's expected at this stage).
**Deploy:** Hit the hosted `/events/ingest` endpoint manually with curl/Postman, confirm the row lands.

### v0.4 — Event generator
**Goal:** A repeatable way to produce realistic (messy) traffic.
**Build:** `event_simulator.py` with flags for event rate, duplicate probability, and late-arrival delay range. Callable as a script or via `POST /events/simulate`.
**Done when:** running it for 60 seconds produces N events in ClickHouse where you can independently verify the duplicate rate matches what you configured.
**Deploy:** Optional at this stage — this can stay a local/dev-only tool, not part of the production surface.

### v0.5 — Aggregation worker
**Goal:** The core correctness claim of the whole project.
**Build:** `aggregation_job.py` implementing the per-advertiser dedup-and-window logic from the tech spec. Runnable standalone (`python -m app.workers.aggregation_job`) before you wire up scheduling.
**Done when:** you run the generator with a known duplicate/late-event pattern, run the job, and the numbers in `ad_spend_5min` match your hand-calculated expected totals. This test *is* your headline resume claim — write it as an actual automated test, not a manual check.
**Deploy:** Deploy the worker as a scheduled job (Render Cron Jobs, or a simple `cron` inside the worker container running hourly). Confirm it runs on schedule against hosted ClickHouse.

### v0.6 — Query API
**Goal:** Serve the clean data.
**Build:** `GET /advertisers/{id}/spend`, `GET /advertisers/{id}/budget-status`. Reads only from `ad_spend_5min`, never the raw table.
**Done when:** querying returns correct grouped totals, and a test confirms response time stays fast even after generating a large volume of raw events (since the API never touches the raw table, this should hold).
**Deploy:** Hit the hosted endpoint, confirm real numbers come back.

### v0.7 — Observability
**Goal:** Make the system's behavior visible, not a black box.
**Build:** Structured logging (job run duration, rows processed, advertisers processed). A small `job_runs` table logging each aggregation run's stats.
**Done when:** after a few worker runs, you can query `job_runs` and see a clear history.
**Deploy:** Confirm logs/metrics are visible in the hosted environment (Render/Fly log viewer, or the `job_runs` table itself).

### v0.8 — Benchmark & correctness report
**Goal:** Turn the working system into resume-grade evidence.
**Build:** A script that runs the generator at increasing volumes, records query latency and job runtime, and a written report (in `docs/`) with the numbers and the partition/order-key reasoning from the tech spec.
**Done when:** you have a table of "volume vs. latency" you'd be comfortable screen-sharing in an interview.
**Deploy:** N/A — this is a report, not a service change.

### v0.9 — Polish
**Goal:** Make the repo itself reviewable by a stranger in 5 minutes.
**Build:** README with the architecture diagram, setup instructions, and a link to the live deployed API. Clean up `.env.example`, add a short demo GIF/script if you want.
**Done when:** you could hand the repo URL to a recruiter with zero additional explanation needed.

---

## 5. Suggested git workflow

- `main` is always deployable — protect it, require CI to pass before merge.
- One feature branch per version (`feature/v0.3-ingest-endpoint`), merged via PR even if you're solo — it gives you a clean commit history to point to.
- Tag each merged version (`git tag v0.1`, `v0.2`, ...) — this alone is a small but real signal of "I ship incrementally," which is worth mentioning in an interview.
