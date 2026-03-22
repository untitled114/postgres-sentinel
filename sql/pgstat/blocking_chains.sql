-- Blocking chains via pg_locks + pg_stat_activity
WITH RECURSIVE lock_chain AS (
    -- Root blockers: sessions that hold locks blocking others
    SELECT
        blocked.pid AS blocked_pid,
        blocking.pid AS blocking_pid,
        blocked.query AS blocked_query,
        blocking.query AS blocking_query,
        blocked.wait_event_type,
        blocked.wait_event,
        EXTRACT(EPOCH FROM (NOW() - blocked.query_start))::INT * 1000 AS elapsed_ms,
        1 AS chain_depth,
        ARRAY[blocking.pid, blocked.pid] AS chain_path
    FROM pg_locks bl
    JOIN pg_stat_activity blocked ON blocked.pid = bl.pid
    JOIN pg_locks kl ON kl.transactionid = bl.transactionid AND kl.pid <> bl.pid AND kl.granted
    JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
    WHERE NOT bl.granted

    UNION ALL

    -- Recursive: find deeper blocking
    SELECT
        lc.blocked_pid,
        blocking.pid AS blocking_pid,
        lc.blocked_query,
        blocking.query AS blocking_query,
        lc.wait_event_type,
        lc.wait_event,
        lc.elapsed_ms,
        lc.chain_depth + 1,
        lc.chain_path || blocking.pid
    FROM lock_chain lc
    JOIN pg_locks bl ON bl.pid = lc.blocking_pid AND NOT bl.granted
    JOIN pg_locks kl ON kl.transactionid = bl.transactionid AND kl.pid <> bl.pid AND kl.granted
    JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
    WHERE lc.chain_depth < 10
      AND NOT blocking.pid = ANY(lc.chain_path)
)
SELECT
    blocked_pid,
    blocking_pid,
    LEFT(blocked_query, 500) AS blocked_query,
    LEFT(blocking_query, 500) AS blocking_query,
    wait_event_type,
    wait_event,
    elapsed_ms,
    chain_depth,
    chain_path
FROM lock_chain
ORDER BY chain_depth, elapsed_ms DESC;
