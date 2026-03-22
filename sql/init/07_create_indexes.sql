-- 07_create_indexes.sql
-- Performance indexes

-- Predictions
CREATE INDEX IF NOT EXISTS ix_predictions_game_date
    ON predictions (game_date DESC);

CREATE INDEX IF NOT EXISTS ix_predictions_model
    ON predictions (model_version, market);

-- Line snapshots
CREATE INDEX IF NOT EXISTS ix_line_snapshots_captured
    ON line_snapshots (captured_at DESC);

-- Pick history
CREATE INDEX IF NOT EXISTS ix_pick_history_game_date
    ON pick_history (game_date DESC);

-- Pipeline runs
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_status
    ON pipeline_runs (status, started_at DESC);

-- Health snapshots
CREATE INDEX IF NOT EXISTS ix_health_snapshots_captured
    ON health_snapshots (captured_at DESC);

-- Incidents
CREATE INDEX IF NOT EXISTS ix_incidents_status
    ON incidents (status);

CREATE INDEX IF NOT EXISTS ix_incidents_detected
    ON incidents (detected_at DESC);

CREATE INDEX IF NOT EXISTS ix_incidents_dedup
    ON incidents (dedup_key)
    WHERE dedup_key IS NOT NULL;

-- Fact table (BRIN for ordered date_key)
CREATE INDEX IF NOT EXISTS ix_fact_predictions_datekey
    ON fact_predictions USING BRIN (date_key);

-- Governance
CREATE INDEX IF NOT EXISTS ix_data_catalog_phi
    ON data_catalog (is_phi)
    WHERE is_phi = TRUE;

CREATE INDEX IF NOT EXISTS ix_phi_access_log_accessed
    ON phi_access_log (accessed_at DESC);

-- Feature drift
CREATE INDEX IF NOT EXISTS ix_feature_drift_checked
    ON feature_drift_log (checked_at DESC);

-- API health
CREATE INDEX IF NOT EXISTS ix_api_health_checked
    ON api_health_log (checked_at DESC);
