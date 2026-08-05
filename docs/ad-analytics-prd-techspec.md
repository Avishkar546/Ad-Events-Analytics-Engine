# Ad Events Analytics Engine — PRD & Technical Specification

**Author:** Avishkar
**Status:** Draft — pre-implementation
**Inspired by:** Zepto TechXPress, "A Billion Events a Day: How We Built Ads Analytics That Actually Works"

---

## Part 1 — Product Requirements Document (PRD)

### 1.1 Problem Statement

An ad platform receives a continuous stream of view/click events. The business needs to know, at any moment, how much each advertiser has spent — sliced by campaign, category, device, and time — and this number must be **exact**, because it also drives billing. Two properties of event streams make this hard:

- **Duplicates**: the same event can be received more than once (client retries, network issues).
- **Late arrival**: an event's *occurrence time* and its *arrival time* at the server can differ by minutes to hours.

A naive "count on insert" or "sum on query" approach breaks under both conditions at scale.

### 1.2 Goals

| # | Goal |
|---|------|
| G1 | Ingest ad events (impressions, clicks) at a configurable rate via API |
| G2 | Guarantee each logical event is counted exactly once, regardless of duplicate deliveries |
| G3 | Correctly attribute late-arriving events to their true event-time window, not arrival time |
| G4 | Serve advertiser spend queries from pre-aggregated data — no live scans of raw events |
| G5 | Demonstrate correctness with a reproducible test: inject duplicates/late events, prove totals stay accurate |

### 1.3 Non-Goals (out of scope for v1)

- Real-time (sub-second) budget enforcement — v1 recomputes hourly, not per-event
- Multi-region / multi-datacenter replication
- Fraud detection on events
- A production-scale load target (billions/day) — the goal is to demonstrate the *pattern* at a scale you can run on a laptop/small VM, with load numbers reported honestly

### 1.4 Users / Consumers of this system

- **Advertiser** — views their own spend via API/dashboard
- **Internal billing** (simulated) — reads the same summary table to charge advertisers
- **You (interviewer-facing)** — the system itself is the primary "user" in the sense that its correctness under duplicate/late-event injection is the thing being demonstrated

### 1.5 Success Criteria

- A load test with X% duplicate rate and Y-minute late-arrival delay produces spend totals matching hand-computed expected values, within one aggregation cycle
- Query latency for "advertiser spend, last 24h, grouped by campaign" stays under a documented target (e.g. <200ms) as raw event volume grows
- A written benchmark comparing "query summary table" vs "query raw table directly" at increasing data volumes

---

## Part 2 — Technical Specification

### 2.1 Architecture Overview

```
                 ┌─────────────────────┐
  Event          │   Event Generator     │
  Producer  ───▶ │ (simulates traffic,   │
  (simulated)    │  injects dupes/late)  │
                 └──────────┬───────────┘
                            │ POST /events/ingest
                            ▼
                 ┌─────────────────────┐
                 │   FastAPI Ingest      │
                 │   Endpoint             │
                 └──────────┬───────────┘
                            │ INSERT
                            ▼
                 ┌─────────────────────┐
                 │  ClickHouse            │
                 │  ad_events_raw         │  ← messy: dupes + late events allowed
                 │  (ReplacingMergeTree)  │
                 └──────────┬───────────┘
                            │
                  hourly    │  scheduled worker
                  cron job  │  (dedup + window + write)
                            ▼
                 ┌─────────────────────┐
                 │  ClickHouse            │
                 │  ad_spend_5min         │  ← clean: source of truth for reads
                 └──────────┬───────────┘
                            │ SELECT
                            ▼
                 ┌─────────────────────┐
                 │  FastAPI Query API     │
                 │  /advertisers/{id}/    │
                 │  spend, /budget-status │
                 └──────────┬───────────┘
                            │
                            ▼
                     Advertiser / Dashboard
```

### 2.2 Components

| Component | Responsibility | Tech |
|---|---|---|
| Event Generator | Simulate realistic event traffic, with controls for duplicate rate and late-arrival delay | Python script or FastAPI endpoint |
| Ingest API | Accept raw events, write to ClickHouse with no processing | FastAPI |
| Raw event store | Durable log of all received events, deduped only at merge time | ClickHouse (`ReplacingMergeTree`) |
| Dedup view | Read-time guarantee of deduplication regardless of merge state | ClickHouse `VIEW` using `argMax` |
| Aggregation worker | Scheduled job: dedup, window, and write clean aggregates | Python (APScheduler or cron + script) |
| Aggregate store | Small, fast-to-query summary table | ClickHouse (`ReplacingMergeTree`) |
| Query API | Serve advertiser spend and budget-status reads | FastAPI |

### 2.3 Data Model

**Raw event (as received):**

```json
{
  "event_id": "uuid",
  "event_type": "impression | click",
  "advertiser_id": "int",
  "campaign_id": "int",
  "category": "string",
  "device": "mobile | desktop",
  "cost": "decimal",
  "event_timestamp": "ISO8601 — when it happened",
  "ingested_at": "ISO8601 — when we received it, set server-side"
}
```

**ClickHouse tables:** see schema in project notes — `ad_events_raw` (partition by `toDate(event_timestamp)`, order by `(advertiser_id, campaign_id, event_id)`), `ad_events_deduped` view, `ad_spend_5min` aggregate table.

### 2.4 Aggregation Job — Algorithm

```
every 1 hour:
  active_advertisers = SELECT DISTINCT advertiser_id
                        FROM ad_events_raw
                        WHERE ingested_at >= now() - 1 hour

  for each advertiser_id in active_advertisers:
    dedup + bucket events from the last 4 hours
    (4h lookback = tolerance window for late events)
    OVERWRITE (not increment) the affected 5-minute buckets
    in ad_spend_5min
```

Two design decisions worth calling out in an interview:
- **Per-advertiser loop, not one global query** — keeps memory/compute proportional to one advertiser's data, not total platform volume.
- **Overwrite, not increment** — makes the job safely re-runnable; if it fails halfway and reruns, you don't double-add.

### 2.5 API Contract (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/events/ingest` | Accept a raw event |
| POST | `/events/simulate` | Trigger the generator with configurable duplicate/late-event rates |
| GET | `/advertisers/{id}/spend?from=&to=&group_by=` | Query aggregated spend |
| GET | `/advertisers/{id}/budget-status` | Spend vs. a configured budget |

### 2.6 Non-Functional Requirements

- **Correctness over speed** for v1 — a slow-but-correct aggregation job is acceptable; a fast-but-wrong one is not.
- **Idempotency** — rerunning the aggregation job for the same window must produce the same result.
- **Observability** — job run duration and row counts processed should be logged, so you can produce the benchmark numbers the PRD asks for.

### 2.7 Milestones

1. ClickHouse schema stood up, manually verified with a hand-inserted duplicate + late event
2. Event generator built with duplicate/late-arrival controls
3. Aggregation worker implemented and verified against generator output
4. FastAPI layer wrapping the summary table
5. Benchmark write-up: query latency and job runtime vs. data volume, plus the correctness test results

### 2.8 Open Questions (to resolve before/while building)

- Exact duplicate rate and late-arrival distribution to simulate — pick numbers you can justify (e.g. 2% duplicate rate, late events up to 90 minutes)
- Budget-status semantics: hard cutoff or soft warning at threshold?
- Whether to add the optional natural-language query layer in v1 or as a v2 stretch
