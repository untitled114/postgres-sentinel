-- Current lock waiters
SELECT
    blocked.pid AS waiting_pid,
    blocked.usename AS waiting_user,
    LEFT(blocked.query, 500) AS waiting_query,
    blocked.wait_event_type,
    blocked.wait_event,
    EXTRACT(EPOCH FROM (NOW() - blocked.query_start))::INT * 1000 AS wait_time_ms,
    blocking.pid AS blocking_pid,
    blocking.usename AS blocking_user,
    LEFT(blocking.query, 500) AS blocking_query,
    blocking.state AS blocking_state
FROM pg_stat_activity blocked
JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
JOIN pg_locks kl ON kl.transactionid = bl.transactionid AND kl.pid <> bl.pid AND kl.granted
JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
WHERE blocked.pid <> pg_backend_pid()
ORDER BY blocked.query_start;
