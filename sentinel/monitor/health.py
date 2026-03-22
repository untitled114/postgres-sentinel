"""Health collector — reads PostgreSQL stats, saves snapshots, evaluates thresholds."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sentinel.config.models import SentinelConfig
from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager

logger = logging.getLogger(__name__)


class HealthCollector:
    """Collects health metrics from PostgreSQL and evaluates thresholds."""

    def __init__(self, db: ConnectionManager, config: SentinelConfig):
        self.db = db
        self.config = config
        self.thresholds = config.thresholds

    def collect_snapshot(self) -> dict[str, Any]:
        """Run fn_capture_health_snapshot and evaluate thresholds."""
        try:
            rows = self.db.execute_proc("fn_capture_health_snapshot")
            if not rows:
                return self._error_snapshot("No data returned from health snapshot")
            snapshot = rows[0]
        except DatabaseQueryError as e:
            logger.error("Failed to capture health snapshot: %s", e)
            return self._error_snapshot(str(e))

        alerts = self._evaluate_thresholds(snapshot)
        status = self._compute_status(alerts)

        # Update the snapshot status in DB
        if snapshot.get("id"):
            try:
                self.db.execute_nonquery(
                    "UPDATE health_snapshots SET status = %s, details = %s WHERE id = %s",
                    (status, json.dumps(alerts), snapshot["id"]),
                )
            except DatabaseQueryError as e:
                logger.warning("Failed to update snapshot status: %s", e)

        snapshot["status"] = status
        snapshot["alerts"] = alerts
        return snapshot

    def get_latest(self) -> dict[str, Any] | None:
        """Get the most recent health snapshot."""
        rows = self.db.execute_query(
            "SELECT * FROM health_snapshots ORDER BY id DESC LIMIT 1"
        )
        return rows[0] if rows else None

    def get_history(self, hours: int = 1) -> list[dict[str, Any]]:
        """Get health snapshot history for the last N hours."""
        return self.db.execute_query(
            "SELECT * FROM health_snapshots "
            "WHERE captured_at >= NOW() - INTERVAL '%s hours' "
            "ORDER BY captured_at DESC",
            (hours,),
        )

    def get_sql_health(self) -> dict[str, Any]:
        """Quick PostgreSQL connectivity and version check."""
        try:
            rows = self.db.execute_query(
                "SELECT version() AS version, "
                "current_setting('server_version') AS server_version, "
                "current_database() AS current_db, "
                "NOW() AS server_time"
            )
            return {"connected": True, **rows[0]} if rows else {"connected": False}
        except DatabaseQueryError as e:
            return {"connected": False, "error": str(e)}

    def _evaluate_thresholds(self, snapshot: dict) -> list[dict[str, Any]]:
        """Check snapshot values against configured thresholds."""
        alerts = []
        t = self.thresholds

        cpu = snapshot.get("cpu_percent") or 0
        if cpu >= t.cpu_percent_critical:
            alerts.append(
                {
                    "metric": "cpu",
                    "level": "critical",
                    "value": cpu,
                    "threshold": t.cpu_percent_critical,
                }
            )
        elif cpu >= t.cpu_percent_warning:
            alerts.append(
                {
                    "metric": "cpu",
                    "level": "warning",
                    "value": cpu,
                    "threshold": t.cpu_percent_warning,
                }
            )

        mem_used = snapshot.get("memory_used_mb") or 0
        mem_total = snapshot.get("memory_total_mb") or 1
        mem_pct = (mem_used / mem_total) * 100
        if mem_pct >= t.memory_percent_critical:
            alerts.append(
                {
                    "metric": "memory",
                    "level": "critical",
                    "value": round(mem_pct, 1),
                    "threshold": t.memory_percent_critical,
                }
            )
        elif mem_pct >= t.memory_percent_warning:
            alerts.append(
                {
                    "metric": "memory",
                    "level": "warning",
                    "value": round(mem_pct, 1),
                    "threshold": t.memory_percent_warning,
                }
            )

        conns = snapshot.get("connection_count") or 0
        if conns >= t.connection_count_critical:
            alerts.append(
                {
                    "metric": "connections",
                    "level": "critical",
                    "value": conns,
                    "threshold": t.connection_count_critical,
                }
            )
        elif conns >= t.connection_count_warning:
            alerts.append(
                {
                    "metric": "connections",
                    "level": "warning",
                    "value": conns,
                    "threshold": t.connection_count_warning,
                }
            )

        lock_wait = snapshot.get("lock_wait_count") or 0
        if lock_wait >= t.lock_wait_critical:
            alerts.append(
                {
                    "metric": "lock_wait",
                    "level": "critical",
                    "value": lock_wait,
                    "threshold": t.lock_wait_critical,
                }
            )
        elif lock_wait >= t.lock_wait_warning:
            alerts.append(
                {
                    "metric": "lock_wait",
                    "level": "warning",
                    "value": lock_wait,
                    "threshold": t.lock_wait_warning,
                }
            )

        dead_tuple = snapshot.get("dead_tuple_ratio") or 0
        if dead_tuple >= t.dead_tuple_ratio_critical:
            alerts.append(
                {
                    "metric": "dead_tuple_ratio",
                    "level": "critical",
                    "value": dead_tuple,
                    "threshold": t.dead_tuple_ratio_critical,
                }
            )
        elif dead_tuple >= t.dead_tuple_ratio_warning:
            alerts.append(
                {
                    "metric": "dead_tuple_ratio",
                    "level": "warning",
                    "value": dead_tuple,
                    "threshold": t.dead_tuple_ratio_warning,
                }
            )

        cache_hit = snapshot.get("cache_hit_ratio")
        if cache_hit is not None and cache_hit < 90.0:
            alerts.append(
                {
                    "metric": "cache_hit_ratio",
                    "level": "warning",
                    "value": cache_hit,
                    "threshold": 90.0,
                }
            )

        long_q = snapshot.get("long_query_count") or 0
        if long_q > 0:
            alerts.append(
                {"metric": "long_queries", "level": "warning", "value": long_q, "threshold": 0}
            )

        return alerts

    def _compute_status(self, alerts: list[dict]) -> str:
        """Determine overall status from alerts."""
        if any(a["level"] == "critical" for a in alerts):
            return "critical"
        if any(a["level"] == "warning" for a in alerts):
            return "warning"
        return "healthy"

    def _error_snapshot(self, error: str) -> dict[str, Any]:
        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "alerts": [
                {"metric": "health_check", "level": "critical", "value": error, "threshold": None}
            ],
            "cpu_percent": None,
            "memory_used_mb": None,
            "connection_count": None,
            "lock_wait_count": None,
        }
