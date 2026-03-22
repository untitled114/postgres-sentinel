-- Active queries from pg_stat_activity
SELECT
    pid AS session_id,
    state,
    wait_event_type,
    wait_event,
    EXTRACT(EPOCH FROM (NOW() - query_start))::INT * 1000 AS elapsed_ms,
    EXTRACT(EPOCH FROM (NOW() - query_start))::INT * 1000 AS cpu_ms,
    datname AS database_name,
    LEFT(query, 500) AS current_statement,
    backend_type,
    usename AS login_name,
    client_addr::TEXT AS host_name,
    application_name AS program_name
FROM pg_stat_activity
WHERE state = 'active'
  AND pid <> pg_backend_pid()
  AND backend_type = 'client backend'
ORDER BY query_start ASC;
