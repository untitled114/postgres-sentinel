-- 05_create_etl_functions.sql
-- Sport-suite ETL functions

-- fn_etl_dim_player_scd2: SCD Type 2 merge for dim_player
CREATE OR REPLACE FUNCTION fn_etl_dim_player_scd2()
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INT := 0;
    v_inserted INT := 0;
    rec RECORD;
BEGIN
    -- Close expired rows where source data has changed
    FOR rec IN
        SELECT DISTINCT p.player_name,
               p.market,
               LEFT(p.model_version, 2) AS version_prefix
        FROM predictions p
        WHERE p.game_date >= CURRENT_DATE - INTERVAL '7 days'
    LOOP
        -- Check if current dim_player row differs
        UPDATE dim_player dp
        SET end_date = CURRENT_DATE - 1,
            is_current = FALSE
        WHERE dp.player_name = rec.player_name
          AND dp.is_current = TRUE
          AND dp.row_hash IS DISTINCT FROM
              md5(COALESCE(dp.team, '') || '|' || COALESCE(dp.position, '') || '|' || dp.is_starter::TEXT);

        IF FOUND THEN
            v_updated := v_updated + 1;
        END IF;
    END LOOP;

    -- Insert new current rows for players not yet in dim or whose rows were just closed
    INSERT INTO dim_player (player_name, team, position, is_starter, row_hash, effective_date, is_current)
    SELECT DISTINCT
        p.player_name,
        NULL AS team,
        NULL AS position,
        TRUE AS is_starter,
        md5('' || '|' || '' || '|' || 'true') AS row_hash,
        CURRENT_DATE,
        TRUE
    FROM predictions p
    WHERE NOT EXISTS (
        SELECT 1 FROM dim_player dp
        WHERE dp.player_name = p.player_name
          AND dp.is_current = TRUE
    )
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    RAISE NOTICE 'SCD2 complete: % expired, % inserted', v_updated, v_inserted;
    RETURN v_updated + v_inserted;
END;
$$;


-- fn_etl_model_performance: aggregate pick_history into model_performance by day/model/market
CREATE OR REPLACE FUNCTION fn_etl_model_performance()
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INT := 0;
BEGIN
    INSERT INTO model_performance (model_version, market, period_date, total_picks, wins, losses, win_rate, roi, avg_edge)
    SELECT
        ph.model_version,
        ph.market,
        ph.game_date,
        COUNT(*) AS total_picks,
        COUNT(*) FILTER (WHERE ph.result = 'win') AS wins,
        COUNT(*) FILTER (WHERE ph.result = 'loss') AS losses,
        ROUND(
            COUNT(*) FILTER (WHERE ph.result = 'win')::NUMERIC
            / NULLIF(COUNT(*), 0), 4
        ) AS win_rate,
        NULL::REAL AS roi,
        NULL::REAL AS avg_edge
    FROM pick_history ph
    WHERE ph.result IS NOT NULL
      AND ph.game_date IS NOT NULL
    GROUP BY ph.model_version, ph.market, ph.game_date
    ON CONFLICT (model_version, market, period_date) DO UPDATE SET
        total_picks = EXCLUDED.total_picks,
        wins = EXCLUDED.wins,
        losses = EXCLUDED.losses,
        win_rate = EXCLUDED.win_rate;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;


-- fn_etl_pipeline_metrics: roll up pipeline_runs + incidents into hourly metrics
CREATE OR REPLACE FUNCTION fn_etl_pipeline_metrics(hours_back INT DEFAULT 1)
RETURNS TABLE (
    hour_bucket TIMESTAMPTZ,
    pipeline_runs_total INT,
    pipeline_runs_failed INT,
    incidents_created INT,
    incidents_resolved INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_start TIMESTAMPTZ;
BEGIN
    v_start := date_trunc('hour', NOW() - (hours_back || ' hours')::INTERVAL);

    RETURN QUERY
    SELECT
        date_trunc('hour', ts) AS hour_bucket,
        COALESCE(pr.cnt, 0)::INT AS pipeline_runs_total,
        COALESCE(pr.failed, 0)::INT AS pipeline_runs_failed,
        COALESCE(ic.cnt, 0)::INT AS incidents_created,
        COALESCE(ir.cnt, 0)::INT AS incidents_resolved
    FROM generate_series(v_start, date_trunc('hour', NOW()), '1 hour') AS ts
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INT AS cnt,
               COUNT(*) FILTER (WHERE p.status = 'failed')::INT AS failed
        FROM pipeline_runs p
        WHERE p.started_at >= ts AND p.started_at < ts + INTERVAL '1 hour'
    ) pr ON TRUE
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INT AS cnt
        FROM incidents i
        WHERE i.detected_at >= ts AND i.detected_at < ts + INTERVAL '1 hour'
    ) ic ON TRUE
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INT AS cnt
        FROM incidents i
        WHERE i.resolved_at >= ts AND i.resolved_at < ts + INTERVAL '1 hour'
    ) ir ON TRUE
    ORDER BY ts;
END;
$$;
