-- 04_create_functions.sql
-- Core PL/pgSQL monitoring functions

-- fn_capture_health_snapshot: polls pg_stat views and inserts a health_snapshots row
CREATE OR REPLACE FUNCTION fn_capture_health_snapshot()
RETURNS SETOF health_snapshots
LANGUAGE plpgsql
AS $$
DECLARE
    v_cpu           REAL := 0;
    v_mem_used      REAL := 0;
    v_mem_total     REAL := 0;
    v_conns         INT  := 0;
    v_lock_waits    INT  := 0;
    v_long_queries  INT  := 0;
    v_dead_ratio    REAL := 0;
    v_cache_ratio   REAL := 0;
    v_avg_query_ms  REAL := 0;
    v_status        VARCHAR(20) := 'healthy';
    v_details       JSONB;
    v_id            INT;
BEGIN
    -- Connection count
    SELECT COUNT(*) INTO v_conns
    FROM pg_stat_activity
    WHERE backend_type = 'client backend';

    -- Lock waits
    SELECT COUNT(*) INTO v_lock_waits
    FROM pg_stat_activity
    WHERE wait_event_type = 'Lock';

    -- Long-running queries (> 30s)
    SELECT COUNT(*) INTO v_long_queries
    FROM pg_stat_activity
    WHERE state = 'active'
      AND query_start < NOW() - INTERVAL '30 seconds'
      AND backend_type = 'client backend';

    -- Dead tuple ratio across all user tables
    SELECT COALESCE(
        SUM(n_dead_tup)::REAL / NULLIF(SUM(n_live_tup + n_dead_tup), 0),
        0
    ) INTO v_dead_ratio
    FROM pg_stat_user_tables;

    -- Cache hit ratio
    SELECT COALESCE(
        SUM(blks_hit)::REAL / NULLIF(SUM(blks_hit + blks_read), 0),
        0
    ) INTO v_cache_ratio
    FROM pg_stat_database
    WHERE datname = current_database();

    -- Build details JSON
    v_details := jsonb_build_object(
        'connections', v_conns,
        'lock_waits', v_lock_waits,
        'long_queries', v_long_queries,
        'dead_tuple_ratio', ROUND(v_dead_ratio::NUMERIC, 4),
        'cache_hit_ratio', ROUND(v_cache_ratio::NUMERIC, 4)
    );

    -- Determine status
    IF v_lock_waits > 5 OR v_long_queries > 3 OR v_dead_ratio > 0.2 THEN
        v_status := 'critical';
    ELSIF v_lock_waits > 2 OR v_long_queries > 1 OR v_dead_ratio > 0.1 THEN
        v_status := 'warning';
    END IF;

    -- Insert snapshot
    INSERT INTO health_snapshots (
        captured_at, cpu_percent, memory_used_mb, memory_total_mb,
        connection_count, lock_wait_count, long_query_count,
        dead_tuple_ratio, cache_hit_ratio, avg_query_ms,
        status, details
    ) VALUES (
        NOW(), v_cpu, v_mem_used, v_mem_total,
        v_conns, v_lock_waits, v_long_queries,
        v_dead_ratio, v_cache_ratio, v_avg_query_ms,
        v_status, v_details
    )
    RETURNING id INTO v_id;

    -- Return the inserted row
    RETURN QUERY SELECT * FROM health_snapshots WHERE id = v_id;
END;
$$;


-- fn_cleanup_stale_sessions: terminates idle connections older than idle_minutes
CREATE OR REPLACE FUNCTION fn_cleanup_stale_sessions(idle_minutes INT DEFAULT 60)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INT := 0;
    v_pid   INT;
BEGIN
    FOR v_pid IN
        SELECT pid
        FROM pg_stat_activity
        WHERE state = 'idle'
          AND state_change < NOW() - (idle_minutes || ' minutes')::INTERVAL
          AND backend_type = 'client backend'
          AND pid <> pg_backend_pid()
    LOOP
        PERFORM pg_terminate_backend(v_pid);
        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$;


-- fn_kill_session: terminate a specific backend by PID
CREATE OR REPLACE FUNCTION fn_kill_session(target_pid INT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN pg_terminate_backend(target_pid);
END;
$$;
