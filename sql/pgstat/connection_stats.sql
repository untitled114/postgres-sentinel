-- Connection statistics grouped by user, host, application
SELECT
    usename AS login_name,
    client_addr::TEXT AS host_name,
    application_name AS program_name,
    COUNT(*) AS connection_count,
    COUNT(*) FILTER (WHERE state = 'active') AS active,
    COUNT(*) FILTER (WHERE state = 'idle') AS sleeping,
    MIN(backend_start) AS oldest_connection,
    MAX(state_change) AS last_activity
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY usename, client_addr, application_name
ORDER BY connection_count DESC;
