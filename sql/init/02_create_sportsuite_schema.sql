-- 02_create_sportsuite_schema.sql
-- Sport-suite domain tables for predictions, lines, and performance tracking

CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    player_name     VARCHAR(100) NOT NULL,
    market          VARCHAR(20) NOT NULL,
    model_version   VARCHAR(10) NOT NULL,
    predicted_value REAL,
    line            REAL,
    p_over          REAL,
    edge_pct        REAL,
    direction       VARCHAR(10),
    actual_value    REAL,
    result          VARCHAR(10),
    game_date       DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS line_snapshots (
    id              SERIAL PRIMARY KEY,
    player_name     VARCHAR(100) NOT NULL,
    market          VARCHAR(20) NOT NULL,
    book_name       VARCHAR(50) NOT NULL,
    line_value      REAL NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pick_history (
    id              SERIAL PRIMARY KEY,
    prediction_id   INT REFERENCES predictions(id),
    player_name     VARCHAR(100) NOT NULL,
    market          VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    conviction      VARCHAR(20),
    tier            VARCHAR(10),
    model_version   VARCHAR(10),
    book_name       VARCHAR(50),
    line            REAL,
    result          VARCHAR(10),
    game_date       DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_performance (
    id              SERIAL PRIMARY KEY,
    model_version   VARCHAR(10) NOT NULL,
    market          VARCHAR(20) NOT NULL,
    period_date     DATE NOT NULL,
    total_picks     INT NOT NULL DEFAULT 0,
    wins            INT NOT NULL DEFAULT 0,
    losses          INT NOT NULL DEFAULT 0,
    win_rate        REAL,
    roi             REAL,
    avg_edge        REAL,
    UNIQUE (model_version, market, period_date)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                      SERIAL PRIMARY KEY,
    dag_name                VARCHAR(100) NOT NULL,
    run_id                  VARCHAR(100),
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    status                  VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    rows_processed          INT,
    props_fetched           INT,
    predictions_generated   INT,
    error_message           TEXT
);

CREATE TABLE IF NOT EXISTS feature_drift_log (
    id              SERIAL PRIMARY KEY,
    market          VARCHAR(20) NOT NULL,
    feature_name    VARCHAR(100) NOT NULL,
    z_score         REAL,
    p_value         REAL,
    drift_detected  BOOLEAN NOT NULL DEFAULT FALSE,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_health_log (
    id              SERIAL PRIMARY KEY,
    api_name        VARCHAR(50) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    response_ms     REAL,
    error_message   TEXT,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
