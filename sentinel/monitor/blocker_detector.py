"""Blocking chain detection via pg_locks and pg_stat_activity."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager

logger = logging.getLogger(__name__)


class BlockerDetector:
    """Detects blocking chains in PostgreSQL using pg_locks and pg_stat_activity."""

    def __init__(self, db: ConnectionManager):
        self.db = db

    def detect(self) -> list[dict[str, Any]]:
        """Run blocking chain detection and return results."""
        try:
            sql = """
                WITH RECURSIVE blocking_tree AS (
                    SELECT
                        blocked.pid AS blocked_pid,
                        blocked.usename AS blocked_user,
                        blocked.query AS blocked_query,
                        blocked.wait_event_type AS blocked_wait_type,
                        blocker.pid AS blocker_pid,
                        blocker.usename AS blocker_user,
                        blocker.query AS blocker_query,
                        blocker.pid AS root_blocker_id,
                        0 AS chain_depth
                    FROM pg_stat_activity blocked
                    JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS bp(pid) ON true
                    JOIN pg_stat_activity blocker ON blocker.pid = bp.pid
                    WHERE blocked.pid != blocked.backend_xid::text::int
                       OR blocked.wait_event_type IS NOT NULL

                    UNION ALL

                    SELECT
                        bt.blocked_pid,
                        bt.blocked_user,
                        bt.blocked_query,
                        bt.blocked_wait_type,
                        parent_blocker.pid AS blocker_pid,
                        parent_blocker.usename AS blocker_user,
                        parent_blocker.query AS blocker_query,
                        parent_blocker.pid AS root_blocker_id,
                        bt.chain_depth + 1
                    FROM blocking_tree bt
                    JOIN LATERAL unnest(pg_blocking_pids(bt.blocker_pid)) AS bp(pid) ON true
                    JOIN pg_stat_activity parent_blocker ON parent_blocker.pid = bp.pid
                    WHERE bt.chain_depth < 10
                )
                SELECT DISTINCT
                    blocked_pid,
                    blocked_user,
                    LEFT(blocked_query, 200) AS blocked_query,
                    blocker_pid,
                    blocker_user,
                    LEFT(blocker_query, 200) AS blocker_query,
                    root_blocker_id,
                    chain_depth
                FROM blocking_tree
                ORDER BY chain_depth, blocker_pid
            """
            return self.db.execute_query(sql)
        except DatabaseQueryError as e:
            logger.error("Blocking chain detection failed: %s", e)
            # Fallback: simpler query without recursive CTE
            try:
                return self.db.execute_query(
                    "SELECT "
                    "  blocked.pid AS blocked_pid, "
                    "  blocked.usename AS blocked_user, "
                    "  LEFT(blocked.query, 200) AS blocked_query, "
                    "  blocker.pid AS blocker_pid, "
                    "  blocker.usename AS blocker_user, "
                    "  LEFT(blocker.query, 200) AS blocker_query, "
                    "  blocker.pid AS root_blocker_id, "
                    "  0 AS chain_depth "
                    "FROM pg_stat_activity blocked "
                    "JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS bp(pid) ON true "
                    "JOIN pg_stat_activity blocker ON blocker.pid = bp.pid"
                )
            except DatabaseQueryError:
                return []

    def get_root_blockers(self) -> list[dict[str, Any]]:
        """Get only the root blockers (chain_depth = 0)."""
        chains = self.detect()
        return [c for c in chains if c.get("chain_depth") == 0]

    def get_chain_summary(self) -> dict[str, Any]:
        """Get a summary of current blocking situation."""
        chains = self.detect()
        if not chains:
            return {"blocking": False, "chains": 0, "total_blocked": 0, "max_depth": 0}

        root_blockers = {c["root_blocker_id"] for c in chains}
        max_depth = max(c.get("chain_depth", 0) for c in chains)
        total_blocked = sum(1 for c in chains if c.get("chain_depth", 0) > 0)

        return {
            "blocking": True,
            "chains": len(root_blockers),
            "total_blocked": total_blocked,
            "max_depth": max_depth,
            "root_blockers": list(root_blockers),
            "details": chains,
        }
