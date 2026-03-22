"""Python-based job scheduler — cron-driven SQL execution with logging."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sentinel.config.models import JobConfig
from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager
from sentinel.db.queries import load_sql

logger = logging.getLogger(__name__)


def _parse_simple_cron(cron_expr: str) -> int:
    """Parse a simplified cron expression and return interval in seconds.

    Supports:
        "*/N * * * *"  -> every N minutes
        "*/N * * * * *" -> every N seconds (extended)
        "@every Ns" -> every N seconds
        "@every Nm" -> every N minutes
    """
    if cron_expr.startswith("@every"):
        val = cron_expr.split()[1]
        if val.endswith("s"):
            return int(val[:-1])
        if val.endswith("m"):
            return int(val[:-1]) * 60
        if val.endswith("h"):
            return int(val[:-1]) * 3600
        return int(val)

    parts = cron_expr.strip().split()
    if len(parts) >= 5 and parts[0].startswith("*/"):
        n = int(parts[0][2:])
        return n * 60
    return 60  # default: every minute


class JobRunner:
    """Executes scheduled jobs and logs results to the database."""

    def __init__(self, db: ConnectionManager, jobs: list[JobConfig]):
        self.db = db
        self.jobs = {j.name: j for j in jobs if j.enabled}
        self._last_run: dict[str, float] = {}
        self._running = False

    def get_all_jobs(self) -> list[dict[str, Any]]:
        """Return job configs with schedule info."""
        result = []
        for name, job in self.jobs.items():
            interval = _parse_simple_cron(job.schedule_cron)
            last = self._last_run.get(name)
            result.append(
                {
                    "name": name,
                    "schedule": job.schedule_cron,
                    "interval_seconds": interval,
                    "enabled": job.enabled,
                    "description": job.description,
                    "last_run": (
                        datetime.fromtimestamp(last, tz=timezone.utc).isoformat() if last else None
                    ),
                }
            )
        return result

    def get_history(self, job_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Get job run history."""
        if job_name:
            return self.db.execute_query(
                "SELECT * FROM job_runs WHERE job_name = %s " "ORDER BY started_at DESC LIMIT %s",
                (job_name, limit),
            )
        return self.db.execute_query(
            "SELECT * FROM job_runs ORDER BY started_at DESC LIMIT %s", (limit,)
        )

    def run_job(self, job_name: str) -> dict[str, Any]:
        """Manually trigger a job by name."""
        job = self.jobs.get(job_name)
        if not job:
            return {"error": f"Job not found: {job_name}"}
        return self._execute_job(job)

    def _execute_job(self, job: JobConfig) -> dict[str, Any]:
        """Execute a single job and log the result."""
        start_time = time.time()
        run_id = self._log_start(job.name)

        try:
            sql = self._resolve_sql(job)
            if not sql:
                raise ValueError(f"No SQL defined for job '{job.name}'")

            rows_affected = self.db.execute_nonquery(sql)
            duration_ms = int((time.time() - start_time) * 1000)

            self._log_complete(run_id, "success", duration_ms, rows_affected)
            self._last_run[job.name] = time.time()

            logger.info("Job '%s' completed: %d rows, %dms", job.name, rows_affected, duration_ms)
            return {
                "job_name": job.name,
                "status": "success",
                "rows_affected": rows_affected,
                "duration_ms": duration_ms,
            }

        except (DatabaseQueryError, ValueError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_complete(run_id, "failed", duration_ms, error=str(e))
            logger.error("Job '%s' failed: %s", job.name, e)
            return {
                "job_name": job.name,
                "status": "failed",
                "error": str(e),
                "duration_ms": duration_ms,
            }

    def _resolve_sql(self, job: JobConfig) -> str | None:
        """Get SQL from file or inline."""
        if job.sql_file:
            return load_sql(job.sql_file)
        return job.sql_inline

    def _log_start(self, job_name: str) -> int | None:
        """Log a job run start and return the run ID."""
        try:
            rows = self.db.execute_query(
                "INSERT INTO job_runs (job_name, status) VALUES (%s, 'running') RETURNING id",
                (job_name,),
            )
            return rows[0]["id"] if rows else None
        except DatabaseQueryError as e:
            logger.warning("Failed to log job start: %s", e)
            return None

    def _log_complete(
        self,
        run_id: int | None,
        status: str,
        duration_ms: int,
        rows_affected: int = 0,
        error: str | None = None,
    ) -> None:
        """Update the job run record with completion info."""
        if run_id is None:
            return
        try:
            self.db.execute_nonquery(
                "UPDATE job_runs SET completed_at = NOW(), status = %s, "
                "duration_ms = %s, rows_affected = %s, error_message = %s WHERE id = %s",
                (status, duration_ms, rows_affected, error, run_id),
            )
        except DatabaseQueryError as e:
            logger.warning("Failed to log job completion: %s", e)

    async def run_loop(self) -> None:
        """Background loop: check and run due jobs."""
        self._running = True
        logger.info("Job runner started with %d jobs", len(self.jobs))

        while self._running:
            now = time.time()
            for name, job in self.jobs.items():
                interval = _parse_simple_cron(job.schedule_cron)
                last = self._last_run.get(name, 0)
                if now - last >= interval:
                    try:
                        self._execute_job(job)
                    except (DatabaseQueryError, ValueError) as e:
                        logger.error("Job loop error for '%s': %s", name, e)
            await asyncio.sleep(5)

    def stop(self) -> None:
        """Stop the background job runner."""
        self._running = False
