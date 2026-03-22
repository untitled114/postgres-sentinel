"""Built-in remediation actions."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager

logger = logging.getLogger(__name__)


def kill_blocking_session(db: ConnectionManager, session_id: int, **kwargs) -> dict[str, Any]:
    """Kill a specific session that's blocking others."""
    try:
        db.execute_query("SELECT pg_terminate_backend(%s)", (session_id,))
        return {"success": True, "detail": f"Terminated backend {session_id}"}
    except DatabaseQueryError as e:
        return {"success": False, "detail": f"Failed to terminate backend {session_id}: {e}"}


def cleanup_stale_sessions(
    db: ConnectionManager, idle_minutes: int = 60, **kwargs
) -> dict[str, Any]:
    """Clean up sessions idle for more than N minutes."""
    try:
        rows = db.execute_proc("fn_cleanup_stale_sessions", (idle_minutes,))
        killed = rows[0].get("sessions_killed", 0) if rows else 0
        return {"success": True, "detail": f"Cleaned up {killed} stale sessions"}
    except DatabaseQueryError as e:
        return {"success": False, "detail": f"Stale session cleanup failed: {e}"}


def restart_failed_job(db: ConnectionManager, job_name: str, **kwargs) -> dict[str, Any]:
    """Mark a failed job for re-execution (runner picks it up on next cycle)."""
    try:
        db.execute_nonquery(
            "UPDATE job_runs SET status = 'pending_retry', error_message = "
            "COALESCE(error_message, '') || ' | Remediation: retry scheduled' "
            "WHERE job_name = %s AND status = 'failed' "
            "AND id = (SELECT MAX(id) FROM job_runs WHERE job_name = %s AND status = 'failed')",
            (job_name, job_name),
        )
        return {"success": True, "detail": f"Job '{job_name}' marked for retry"}
    except DatabaseQueryError as e:
        return {"success": False, "detail": f"Failed to restart job '{job_name}': {e}"}


def escalate_to_manual(db: ConnectionManager, **kwargs) -> dict[str, Any]:
    """Escalate incident for manual review — no automatic fix available."""
    return {"success": True, "detail": "Escalated to manual review — no auto-fix available"}


def trigger_pipeline_refresh(db: ConnectionManager, **kwargs) -> dict[str, Any]:
    """Trigger a manual pipeline refresh by inserting a pipeline_runs record."""
    try:
        db.execute_nonquery(
            "INSERT INTO pipeline_runs (dag_name, status, started_at) "
            "VALUES ('manual_refresh', 'triggered', NOW())"
        )
        return {"success": True, "detail": "Pipeline refresh triggered (manual_refresh)"}
    except DatabaseQueryError as e:
        return {"success": False, "detail": f"Pipeline refresh trigger failed: {e}"}


def trigger_line_refresh(db: ConnectionManager, **kwargs) -> dict[str, Any]:
    """Trigger a line data refresh by inserting a pipeline_runs record."""
    try:
        db.execute_nonquery(
            "INSERT INTO pipeline_runs (dag_name, status, started_at) "
            "VALUES ('line_refresh', 'triggered', NOW())"
        )
        return {"success": True, "detail": "Line refresh triggered (line_refresh)"}
    except DatabaseQueryError as e:
        return {"success": False, "detail": f"Line refresh trigger failed: {e}"}


ACTIONS: dict[str, Any] = {
    "kill_blocking_session": kill_blocking_session,
    "cleanup_stale_sessions": cleanup_stale_sessions,
    "restart_failed_job": restart_failed_job,
    "escalate_to_manual": escalate_to_manual,
    "trigger_pipeline_refresh": trigger_pipeline_refresh,
    "trigger_line_refresh": trigger_line_refresh,
}
