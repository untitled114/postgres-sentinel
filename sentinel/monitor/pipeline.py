"""Pipeline monitor — Sport-suite prediction pipeline, win rates, and API health."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.config.models import ThresholdConfig
from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager

logger = logging.getLogger(__name__)


class PipelineMonitor:
    """Monitors Sport-suite pipeline metrics: win rates, predictions, line coverage."""

    def __init__(self, db: ConnectionManager, thresholds: ThresholdConfig):
        self.db = db
        self.thresholds = thresholds
        self._latest_metrics: dict[str, Any] | None = None

    def collect_metrics(self) -> dict[str, Any]:
        """Collect pipeline metrics from predictions, line_snapshots, pick_history, etc."""
        metrics: dict[str, Any] = {}

        # 7-day rolling win rate from model_performance
        try:
            rows = self.db.execute_query(
                "SELECT "
                "  ROUND(AVG(win_rate), 1) AS win_rate_7d, "
                "  SUM(total_picks) AS total_picks_7d, "
                "  SUM(wins) AS wins_7d, "
                "  SUM(losses) AS losses_7d "
                "FROM model_performance "
                "WHERE report_date >= CURRENT_DATE - 7"
            )
            if rows and rows[0].get("win_rate_7d") is not None:
                metrics.update(rows[0])
            else:
                metrics.update(
                    {"win_rate_7d": None, "total_picks_7d": 0, "wins_7d": 0, "losses_7d": 0}
                )
        except DatabaseQueryError as e:
            logger.warning("Failed to collect win rate metrics: %s", e)
            metrics.update({"win_rate_7d": None, "total_picks_7d": 0, "wins_7d": 0, "losses_7d": 0})

        # Today's prediction count
        try:
            rows = self.db.execute_query(
                "SELECT COUNT(*) AS predictions_today "
                "FROM predictions "
                "WHERE created_at >= CURRENT_DATE"
            )
            metrics["predictions_today"] = rows[0]["predictions_today"] if rows else 0
        except DatabaseQueryError as e:
            logger.warning("Failed to collect prediction count: %s", e)
            metrics["predictions_today"] = 0

        # Prediction staleness (hours since last prediction)
        try:
            rows = self.db.execute_query(
                "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) / 3600.0 "
                "AS hours_since_last_prediction "
                "FROM predictions"
            )
            val = rows[0]["hours_since_last_prediction"] if rows else None
            metrics["hours_since_last_prediction"] = round(val, 1) if val is not None else None
        except DatabaseQueryError as e:
            logger.warning("Failed to collect prediction staleness: %s", e)
            metrics["hours_since_last_prediction"] = None

        # Today's line snapshot volume
        try:
            rows = self.db.execute_query(
                "SELECT COUNT(*) AS line_snapshots_today "
                "FROM line_snapshots "
                "WHERE captured_at >= CURRENT_DATE"
            )
            metrics["line_snapshots_today"] = rows[0]["line_snapshots_today"] if rows else 0
        except DatabaseQueryError as e:
            logger.warning("Failed to collect line snapshot volume: %s", e)
            metrics["line_snapshots_today"] = 0

        # Conviction distribution from pick_history
        try:
            rows = self.db.execute_query(
                "SELECT "
                "  conviction, "
                "  COUNT(*) AS cnt "
                "FROM pick_history "
                "WHERE game_date = CURRENT_DATE "
                "GROUP BY conviction"
            )
            conviction_dist = {r["conviction"]: r["cnt"] for r in rows} if rows else {}
            metrics["conviction_distribution"] = conviction_dist
            total_picks = sum(conviction_dist.values())
            locked = conviction_dist.get("LOCKED", 0)
            metrics["conviction_locked_pct"] = (
                round(100.0 * locked / total_picks, 1) if total_picks > 0 else 0.0
            )
        except DatabaseQueryError as e:
            logger.warning("Failed to collect conviction distribution: %s", e)
            metrics["conviction_distribution"] = {}
            metrics["conviction_locked_pct"] = 0.0

        # Latest pipeline run statuses
        try:
            rows = self.db.execute_query(
                "SELECT dag_name, status, started_at, completed_at "
                "FROM pipeline_runs "
                "WHERE started_at >= CURRENT_DATE "
                "ORDER BY started_at DESC "
                "LIMIT 10"
            )
            metrics["pipeline_runs_today"] = rows or []
        except DatabaseQueryError as e:
            logger.warning("Failed to collect pipeline runs: %s", e)
            metrics["pipeline_runs_today"] = []

        # API health
        try:
            rows = self.db.execute_query(
                "SELECT "
                "  api_name, status, response_ms, checked_at "
                "FROM api_health_log "
                "WHERE checked_at = ("
                "  SELECT MAX(checked_at) FROM api_health_log"
                ")"
            )
            metrics["api_health"] = rows or []
            if rows:
                response_times = [r["response_ms"] for r in rows if r.get("response_ms")]
                metrics["avg_api_response_ms"] = (
                    round(sum(response_times) / len(response_times), 1) if response_times else 0.0
                )
                metrics["apis_down"] = sum(1 for r in rows if r.get("status") == "down")
            else:
                metrics["avg_api_response_ms"] = 0.0
                metrics["apis_down"] = 0
        except DatabaseQueryError as e:
            logger.warning("Failed to collect API health: %s", e)
            metrics["api_health"] = []
            metrics["avg_api_response_ms"] = 0.0
            metrics["apis_down"] = 0

        # Feature drift alert count
        try:
            rows = self.db.execute_query(
                "SELECT COUNT(*) AS drift_alerts "
                "FROM feature_drift_log "
                "WHERE logged_at >= NOW() - INTERVAL '24 hours' "
                "  AND drift_detected = true"
            )
            metrics["drift_alerts_24h"] = rows[0]["drift_alerts"] if rows else 0
        except DatabaseQueryError as e:
            logger.warning("Failed to collect drift alerts: %s", e)
            metrics["drift_alerts_24h"] = 0

        self._latest_metrics = metrics
        return metrics

    def evaluate_thresholds(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate pipeline metrics against configured thresholds."""
        alerts: list[dict[str, Any]] = []
        t = self.thresholds

        # Win rate below warning/critical
        win_rate = metrics.get("win_rate_7d")
        if win_rate is not None:
            if win_rate <= t.win_rate_7d_critical:
                alerts.append(
                    {
                        "metric": "win_rate_7d",
                        "level": "critical",
                        "value": win_rate,
                        "threshold": t.win_rate_7d_critical,
                    }
                )
            elif win_rate <= t.win_rate_7d_warning:
                alerts.append(
                    {
                        "metric": "win_rate_7d",
                        "level": "warning",
                        "value": win_rate,
                        "threshold": t.win_rate_7d_warning,
                    }
                )

        # Line snapshot volume below threshold
        snapshots = metrics.get("line_snapshots_today", 0)
        if snapshots <= t.line_snapshot_volume_critical:
            alerts.append(
                {
                    "metric": "line_snapshot_volume",
                    "level": "critical",
                    "value": snapshots,
                    "threshold": t.line_snapshot_volume_critical,
                }
            )
        elif snapshots <= t.line_snapshot_volume_warning:
            alerts.append(
                {
                    "metric": "line_snapshot_volume",
                    "level": "warning",
                    "value": snapshots,
                    "threshold": t.line_snapshot_volume_warning,
                }
            )

        # Prediction staleness
        hours = metrics.get("hours_since_last_prediction")
        if hours is not None and hours > t.prediction_staleness_hours:
            alerts.append(
                {
                    "metric": "prediction_staleness",
                    "level": "warning",
                    "value": hours,
                    "threshold": t.prediction_staleness_hours,
                }
            )

        # Conviction LOCKED % above threshold
        locked_pct = metrics.get("conviction_locked_pct", 0.0)
        if locked_pct > t.conviction_locked_pct_warning:
            alerts.append(
                {
                    "metric": "conviction_locked_pct",
                    "level": "warning",
                    "value": locked_pct,
                    "threshold": t.conviction_locked_pct_warning,
                }
            )

        # API response time above threshold
        avg_ms = metrics.get("avg_api_response_ms", 0.0)
        if avg_ms >= t.api_response_ms_critical:
            alerts.append(
                {
                    "metric": "api_response_ms",
                    "level": "critical",
                    "value": avg_ms,
                    "threshold": t.api_response_ms_critical,
                }
            )
        elif avg_ms >= t.api_response_ms_warning:
            alerts.append(
                {
                    "metric": "api_response_ms",
                    "level": "warning",
                    "value": avg_ms,
                    "threshold": t.api_response_ms_warning,
                }
            )

        return alerts

    def get_latest_metrics(self) -> dict[str, Any] | None:
        """Return cached metrics from last collect_metrics() call."""
        return self._latest_metrics
