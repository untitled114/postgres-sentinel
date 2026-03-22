"""Remediation engine — pattern-match incidents to actions, execute, log."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager
from sentinel.monitor.incident_manager import IncidentManager
from sentinel.remediation.actions import ACTIONS

logger = logging.getLogger(__name__)

# Pattern -> action mapping
DEFAULT_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern": "cpu",
        "action": "cleanup_stale_sessions",
        "params": {"idle_minutes": 5},
    },
    {
        "pattern": "memory",
        "action": "cleanup_stale_sessions",
        "params": {"idle_minutes": 10},
    },
    {
        "pattern": "lock_wait",
        "action": "cleanup_stale_sessions",
        "params": {"idle_minutes": 30},
    },
    {
        "pattern": "long_running",
        "action": "cleanup_stale_sessions",
        "params": {"idle_minutes": 5},
    },
    {
        "pattern": "prediction_staleness",
        "action": "trigger_pipeline_refresh",
        "params": {},
    },
    {
        "pattern": "line_snapshot_volume",
        "action": "trigger_line_refresh",
        "params": {},
    },
    {
        "pattern": "win_rate_7d",
        "action": "escalate_to_manual",
        "params": {},
    },
    {
        "pattern": "api_response",
        "action": "restart_failed_job",
        "params": {"job_name": "api_health_check"},
    },
    {
        "pattern": "feature_null_rate",
        "action": "trigger_pipeline_refresh",
        "params": {},
    },
    {
        "pattern": "chaos:connection_flood",
        "action": "cleanup_stale_sessions",
        "params": {"idle_minutes": 1},
    },
    {
        "pattern": "chaos:api_blackout",
        "action": "trigger_line_refresh",
        "params": {},
    },
    {
        "pattern": "chaos:dag_overlap",
        "action": "cleanup_stale_sessions",
        "params": {"idle_minutes": 1},
    },
    {
        "pattern": "chaos:feature_drift",
        "action": "escalate_to_manual",
        "params": {},
    },
    {
        "pattern": "chaos:conviction_collapse",
        "action": "trigger_pipeline_refresh",
        "params": {},
    },
    {
        "pattern": "chaos:line_ingestion_drop",
        "action": "trigger_line_refresh",
        "params": {},
    },
    {
        "pattern": "chaos:prediction_stale",
        "action": "trigger_pipeline_refresh",
        "params": {},
    },
]


class RemediationEngine:
    """Matches incidents to remediation actions and executes them."""

    def __init__(
        self,
        db: ConnectionManager,
        incident_manager: IncidentManager,
        patterns: list[dict[str, Any]] | None = None,
    ):
        self.db = db
        self.incident_manager = incident_manager
        self.patterns = patterns or DEFAULT_PATTERNS

    def attempt_remediation(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Try to auto-remediate an incident."""
        incident_type = incident.get("incident_type", "")
        incident_id = incident["id"]

        # Find matching pattern
        matched = None
        for p in self.patterns:
            if p["pattern"] in incident_type:
                matched = p
                break

        if not matched:
            logger.info("No remediation pattern for incident type: %s", incident_type)
            return {"remediated": False, "reason": "No matching pattern"}

        action_name = matched["action"]
        action_fn = ACTIONS.get(action_name)
        if not action_fn:
            logger.error("Unknown remediation action: %s", action_name)
            return {"remediated": False, "reason": f"Unknown action: {action_name}"}

        # Transition to remediating
        self.incident_manager.update_status(incident_id, "remediating")

        # Execute action
        logger.info("Executing remediation '%s' for incident %d", action_name, incident_id)
        result = action_fn(self.db, **matched.get("params", {}))

        # Log result
        self._log_remediation(incident_id, action_name, result)

        if result.get("success"):
            self.incident_manager.update_status(incident_id, "resolved", resolved_by="auto")
            return {"remediated": True, "action": action_name, "detail": result.get("detail")}
        else:
            # Escalate on failure
            self.incident_manager.update_status(incident_id, "escalated")
            return {
                "remediated": False,
                "action": action_name,
                "detail": result.get("detail"),
                "escalated": True,
            }

    def remediate_open_incidents(self) -> list[dict[str, Any]]:
        """Auto-remediate all open incidents."""
        open_incidents = self.incident_manager.list_open()
        results = []
        for incident in open_incidents:
            if incident["status"] in ("detected", "investigating"):
                result = self.attempt_remediation(incident)
                results.append({"incident_id": incident["id"], **result})
        return results

    def _log_remediation(self, incident_id: int, action_name: str, result: dict[str, Any]) -> None:
        """Log a remediation attempt."""
        try:
            self.db.execute_nonquery(
                "INSERT INTO remediation_log (incident_id, action_name, success, details) "
                "VALUES (%s, %s, %s, %s)",
                (
                    incident_id,
                    action_name,
                    1 if result.get("success") else 0,
                    result.get("detail", ""),
                ),
            )
        except DatabaseQueryError as e:
            logger.warning("Failed to log remediation: %s", e)
