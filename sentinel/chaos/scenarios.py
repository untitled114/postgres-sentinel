"""Chaos scenarios targeting real Sport-Suite tables in sportsuite DB."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.core.exceptions import DatabaseQueryError
from sentinel.db.connection import ConnectionManager

logger = logging.getLogger(__name__)


class ChaosScenario:
    """Base chaos scenario."""

    name: str = "base"
    description: str = ""
    severity: str = "medium"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------


class LongRunningQuery(ChaosScenario):
    name = "Long Running Query"
    description = "Runs pg_sleep(45) to simulate a stuck query"
    severity = "medium"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        try:
            db.execute_query("SELECT pg_sleep(45)")
            return {"triggered": True, "detail": "45-second pg_sleep executed"}
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"Long query started (may timeout): {e}"}


class ConnectionFlood(ChaosScenario):
    name = "Connection Flood"
    description = "Opens 20 concurrent connections to stress the pool"
    severity = "high"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        opened = 0
        conns = []
        try:
            for _ in range(20):
                conn = db.get_connection()
                conns.append(conn)
                opened += 1
            return {"triggered": True, "detail": f"Opened {opened} connections"}
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"Opened {opened} before error: {e}"}
        finally:
            for c in conns:
                try:
                    c.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Pipeline Failures
# ---------------------------------------------------------------------------


class DagOverlap(ChaosScenario):
    """Simulate overlapping pipeline runs."""

    name = "DAG Overlap"
    description = "Creates 2 concurrent running pipeline_runs for same date"
    severity = "medium"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        import uuid

        try:
            for i in range(2):
                db.execute_nonquery(
                    "INSERT INTO axiom.pipeline_runs "
                    "(run_id, run_date, run_number, run_type, started_at, status, "
                    " summary) "
                    "VALUES (%s, CURRENT_DATE, %s, 'full', NOW() - INTERVAL '%s minutes', "
                    "'running', '{}'::jsonb)",
                    (str(uuid.uuid4()), 99 + i, str(i * 10)),
                )
            return {"triggered": True, "detail": "2 concurrent pipeline_runs created"}
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"DAG overlap partial: {e}"}


class ExtractorDefaultInjection(ChaosScenario):
    """Write a pipeline_run with 0 feature count to trigger regression alert."""

    name = "Extractor Default Injection"
    description = "Writes a pipeline_run with 0 feature count"
    severity = "high"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        import json
        import uuid

        try:
            db.execute_nonquery(
                "INSERT INTO axiom.pipeline_runs "
                "(run_id, run_date, run_number, run_type, started_at, ended_at, "
                " status, duration_ms, summary, anomalies) "
                "VALUES (%s, CURRENT_DATE, 98, 'full', NOW(), NOW(), 'success', 1000, "
                "%s, %s)",
                (
                    str(uuid.uuid4()),
                    json.dumps({"feature_count": 0, "picks_generated": 0}),
                    json.dumps(
                        [
                            {
                                "type": "feature_count_regression",
                                "severity": "critical",
                                "message": "CHAOS: Feature count forced to 0",
                            }
                        ]
                    ),
                ),
            )
            return {"triggered": True, "detail": "Pipeline run with 0 features injected"}
        except DatabaseQueryError as e:
            return {"triggered": False, "detail": str(e)}


class LineIngestionDrop(ChaosScenario):
    """Delete today's line snapshots to simulate ingestion failure."""

    name = "Line Ingestion Drop"
    description = "Deletes today's line snapshots"
    severity = "high"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        try:
            affected = db.execute_nonquery(
                "DELETE FROM intelligence.nba_line_snapshots " "WHERE game_date = CURRENT_DATE"
            )
            return {"triggered": True, "detail": f"Deleted {affected} line snapshots from today"}
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"Line drop partial: {e}"}


# ---------------------------------------------------------------------------
# Model Failures
# ---------------------------------------------------------------------------


class ModelFileMissing(ChaosScenario):
    """Point model_registry pkl_path to a nonexistent file."""

    name = "Model File Missing"
    description = "Updates model_registry pkl_path to nonexistent file"
    severity = "high"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        try:
            affected = db.execute_nonquery(
                "UPDATE axiom.model_registry "
                "SET pkl_path = '/nonexistent/chaos_test_model.pkl' "
                "WHERE status = 'production' "
                "AND market = 'POINTS'"
            )
            return {
                "triggered": affected > 0,
                "detail": f"Updated {affected} POINTS production model to missing pkl path",
            }
        except DatabaseQueryError as e:
            return {"triggered": False, "detail": str(e)}


class ConvictionCollapse(ChaosScenario):
    """Downgrade all LOCKED picks to SKIP for today."""

    name = "Conviction Collapse"
    description = "Downgrades all LOCKED picks to SKIP"
    severity = "high"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        try:
            affected = db.execute_nonquery(
                "UPDATE axiom.axiom_conviction "
                "SET conviction_label = 'SKIP', conviction = 0.0 "
                "WHERE conviction_label = 'LOCKED' AND run_date = CURRENT_DATE"
            )
            return {"triggered": True, "detail": f"Downgraded {affected} LOCKED → SKIP"}
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"Conviction collapse partial: {e}"}


class WinRateCrash(ChaosScenario):
    """Inject 7 days of losing predictions to trigger retraining."""

    name = "Win Rate Crash"
    description = "Inserts 7 days of 45% win rate predictions"
    severity = "high"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        try:
            injected = 0
            for day_offset in range(7):
                for i in range(20):
                    is_hit = i < 9  # 9/20 = 45%
                    db.execute_nonquery(
                        "INSERT INTO axiom.nba_prediction_history "
                        "(run_date, run_number, run_timestamp, player_name, stat_type, "
                        " model_version, line, p_over, edge, book, is_hit, actual_result) "
                        "VALUES (CURRENT_DATE - %s, 1, NOW(), %s, 'POINTS', 'xl', "
                        " 25.5, 0.65, 0.10, 'DraftKings', %s, %s)",
                        (
                            day_offset,
                            f"Chaos Player {i}",
                            is_hit,
                            26.0 if is_hit else 20.0,
                        ),
                    )
                    injected += 1
            return {
                "triggered": True,
                "detail": f"Injected {injected} predictions (45% WR x 7 days)",
            }
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"Win rate crash partial: {e}"}


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


class PredictionStaleness(ChaosScenario):
    """Delete today's predictions to trigger freshness alert."""

    name = "Prediction Staleness"
    description = "Deletes today's predictions"
    severity = "medium"

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        try:
            affected = db.execute_nonquery(
                "DELETE FROM axiom.nba_prediction_history " "WHERE run_date = CURRENT_DATE"
            )
            return {"triggered": True, "detail": f"Deleted {affected} predictions from today"}
        except DatabaseQueryError as e:
            return {"triggered": True, "detail": f"Prediction stale partial: {e}"}


BUILTIN_SCENARIOS: dict[str, type[ChaosScenario]] = {
    "Long Running Query": LongRunningQuery,
    "Connection Flood": ConnectionFlood,
    "DAG Overlap": DagOverlap,
    "Extractor Default Injection": ExtractorDefaultInjection,
    "Line Ingestion Drop": LineIngestionDrop,
    "Model File Missing": ModelFileMissing,
    "Conviction Collapse": ConvictionCollapse,
    "Win Rate Crash": WinRateCrash,
    "Prediction Staleness": PredictionStaleness,
}
