-- 06_create_governance_schema.sql
-- Data catalog, lineage tracking, and PHI access audit

CREATE TABLE IF NOT EXISTS data_catalog (
    id              SERIAL PRIMARY KEY,
    schema_name     VARCHAR(100) NOT NULL DEFAULT 'public',
    table_name      VARCHAR(100) NOT NULL,
    column_name     VARCHAR(100) NOT NULL,
    data_type       VARCHAR(100),
    description     TEXT,
    is_phi          BOOLEAN NOT NULL DEFAULT FALSE,
    is_pii          BOOLEAN NOT NULL DEFAULT FALSE,
    phi_category    VARCHAR(50),
    masking_rule    VARCHAR(50),
    retention_days  INT,
    classification  VARCHAR(50),
    owner           VARCHAR(100),
    last_scanned_at TIMESTAMPTZ,
    UNIQUE (schema_name, table_name, column_name)
);

CREATE TABLE IF NOT EXISTS data_lineage (
    id              SERIAL PRIMARY KEY,
    pipeline_name   VARCHAR(100) NOT NULL,
    execution_id    VARCHAR(100),
    source_table    VARCHAR(200),
    target_table    VARCHAR(200),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    rows_read       INT DEFAULT 0,
    rows_written    INT DEFAULT 0,
    rows_rejected   INT DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB
);

CREATE TABLE IF NOT EXISTS phi_access_log (
    id              SERIAL PRIMARY KEY,
    user_name       VARCHAR(100) NOT NULL,
    action          VARCHAR(50) NOT NULL,
    table_name      VARCHAR(100),
    record_count    INT DEFAULT 0,
    justification   TEXT,
    accessed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
