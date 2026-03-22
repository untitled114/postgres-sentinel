-- 01_create_sentinel_schema.sql
-- Core monitoring tables for Sentinel

CREATE TABLE IF NOT EXISTS health_snapshots (
    id              SERIAL PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent     REAL,
    memory_used_mb  REAL,
    memory_total_mb REAL,
    connection_count INT,
    lock_wait_count  INT,
    long_query_count INT,
    dead_tuple_ratio REAL,
    cache_hit_ratio  REAL,
    avg_query_ms     REAL,
    status          VARCHAR(20) NOT NULL DEFAULT 'healthy'
        CHECK (status IN ('healthy', 'warning', 'critical')),
    details         JSONB
);

CREATE TABLE IF NOT EXISTS incidents (
    id              SERIAL PRIMARY KEY,
    incident_type   VARCHAR(100) NOT NULL,
    severity        VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status          VARCHAR(20) NOT NULL DEFAULT 'detected'
        CHECK (status IN ('detected', 'investigating', 'remediating', 'resolved', 'escalated')),
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_by     VARCHAR(100),
    dedup_key       VARCHAR(200),
    metadata        JSONB
);

CREATE TABLE IF NOT EXISTS job_runs (
    id              SERIAL PRIMARY KEY,
    job_name        VARCHAR(100) NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    duration_ms     INT,
    rows_affected   INT,
    error_message   TEXT,
    output          TEXT
);

CREATE TABLE IF NOT EXISTS validation_results (
    id              SERIAL PRIMARY KEY,
    rule_name       VARCHAR(100) NOT NULL,
    rule_type       VARCHAR(50) NOT NULL,
    table_name      VARCHAR(100),
    column_name     VARCHAR(100),
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    passed          BOOLEAN NOT NULL,
    severity        VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    violation_count INT DEFAULT 0,
    sample_values   JSONB,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS remediation_log (
    id              SERIAL PRIMARY KEY,
    incident_id     INT NOT NULL REFERENCES incidents(id),
    action_name     VARCHAR(100) NOT NULL,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success         BOOLEAN NOT NULL,
    details         TEXT
);

CREATE TABLE IF NOT EXISTS postmortems (
    id              SERIAL PRIMARY KEY,
    incident_id     INT NOT NULL REFERENCES incidents(id),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary         TEXT,
    root_cause      TEXT,
    timeline        TEXT,
    remediation     TEXT,
    lessons_learned TEXT
);
