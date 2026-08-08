-- Append-only log, no dedup needed — plain MergeTree.
CREATE TABLE IF NOT EXISTS job_runs
(
    run_id                UUID,
    job_name              LowCardinality(String),
    started_at            DateTime64(6),
    finished_at           DateTime64(6),
    duration_seconds      Float64,
    advertisers_processed UInt32,
    status                LowCardinality(String),
    error_message         String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY started_at;
