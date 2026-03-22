-- Table statistics: dead tuples, sequential scans, index usage
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS live_tuples,
    n_dead_tup AS dead_tuples,
    CASE WHEN n_live_tup + n_dead_tup > 0
         THEN ROUND(n_dead_tup::NUMERIC / (n_live_tup + n_dead_tup), 4)
         ELSE 0
    END AS dead_tuple_ratio,
    seq_scan,
    idx_scan,
    CASE WHEN seq_scan + idx_scan > 0
         THEN ROUND(idx_scan::NUMERIC / (seq_scan + idx_scan), 4)
         ELSE 0
    END AS index_usage_ratio,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
