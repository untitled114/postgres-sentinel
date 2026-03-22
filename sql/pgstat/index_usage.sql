-- Index usage statistics
SELECT
    s.schemaname,
    s.relname AS table_name,
    s.indexrelname AS index_name,
    s.idx_scan AS scans,
    s.idx_tup_read AS tuples_read,
    s.idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size
FROM pg_stat_user_indexes s
ORDER BY s.idx_scan DESC;
