"""Shared test fixtures and mock database connection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sentinel.config.models import (
    SentinelConfig,
    ThresholdConfig,
    ValidationRuleConfig,
)


class MockConnectionManager:
    """Mock database that stores data in-memory for testing (PostgreSQL patterns)."""

    def __init__(self):
        self._tables: dict[str, list[dict]] = {
            "health_snapshots": [],
            "incidents": [],
            "job_runs": [],
            "validation_results": [],
            "remediation_log": [],
            "postmortems": [],
            "data_catalog": [],
            "data_lineage": [],
            "phi_access_log": [],
            "predictions": [],
            "line_snapshots": [],
            "pick_history": [],
            "model_performance": [],
            "pipeline_runs": [],
            "api_health_log": [],
            "feature_drift_log": [],
        }
        self._id_counters: dict[str, int] = {}
        self._query_log: list[str] = []

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        self._query_log.append(sql)

        # --- Pipeline monitor mock handlers ---
        if "model_performance" in sql and "AVG" in sql and "win_rate" in sql:
            return [{"win_rate_7d": 58.5}]
        if "predictions" in sql and "COUNT" in sql and "CURRENT_DATE" in sql:
            return [{"predictions_today": 42}]
        if "line_snapshots" in sql and "COUNT" in sql and "CURRENT_DATE" in sql:
            return [{"line_snapshots_today": 12500}]
        if "pick_history" in sql and "conviction" in sql and "COUNT" in sql:
            return [
                {"conviction": "LOCKED", "count": 5},
                {"conviction": "STRONG", "count": 12},
                {"conviction": "WATCH", "count": 8},
                {"conviction": "SKIP", "count": 3},
            ]
        if "pipeline_runs" in sql and "ORDER BY" in sql and "LIMIT" in sql:
            return self._tables.get("pipeline_runs", [])[-5:]
        if "api_health_log" in sql and "DISTINCT" in sql:
            return [
                {"api_name": "bettingpros", "status": "healthy", "response_ms": 250},
                {"api_name": "draftkings", "status": "healthy", "response_ms": 180},
            ]
        if "feature_drift_log" in sql and "drift_detected" in sql:
            return [{"drift_alerts": 0}]

        # --- Core Sentinel mock handlers ---
        if "SELECT 1 AS ok" in sql:
            return [{"ok": 1}]
        if "version()" in sql.lower() or "current_database" in sql.lower():
            return [
                {
                    "version": "PostgreSQL 16.2",
                    "server_name": "test",
                    "current_db": "sentinel",
                    "server_time": "2026-03-22",
                }
            ]
        if "health_snapshots" in sql and "ORDER BY" in sql:
            return (
                self._tables.get("health_snapshots", [])[-1:]
                if self._tables.get("health_snapshots")
                else []
            )
        if "INSERT INTO incidents" in sql and "RETURNING" in sql:
            new_id = self._next_id("incidents")
            record = {
                "id": new_id,
                "incident_type": params[0] if params else "",
                "severity": params[1] if len(params) > 1 else "warning",
                "status": "detected",
                "title": params[2] if len(params) > 2 else "",
            }
            self._tables["incidents"].append(record)
            return [record]
        if "incidents" in sql and "NOT IN" in sql:
            return [
                i
                for i in self._tables.get("incidents", [])
                if i.get("status") not in ("resolved", "escalated")
            ]
        if "incidents" in sql and "ORDER BY" in sql and "LIMIT" in sql:
            return self._tables.get("incidents", [])[-1:] if self._tables.get("incidents") else []
        if "incidents" in sql and "WHERE id" in sql:
            target_id = params[-1] if params else None
            return [i for i in self._tables.get("incidents", []) if i.get("id") == target_id][:1]
        if "incidents" in sql:
            return self._tables.get("incidents", [])
        if "job_runs" in sql:
            return self._tables.get("job_runs", [])
        if "validation_results" in sql:
            return self._tables.get("validation_results", [])
        if "postmortems" in sql:
            return self._tables.get("postmortems", [])
        if "information_schema.columns" in sql.lower():
            return [
                {
                    "schema_name": "public",
                    "table_name": "predictions",
                    "column_name": "player_name",
                    "data_type": "varchar",
                },
                {
                    "schema_name": "public",
                    "table_name": "predictions",
                    "column_name": "model_version",
                    "data_type": "varchar",
                },
                {
                    "schema_name": "public",
                    "table_name": "predictions",
                    "column_name": "p_over",
                    "data_type": "real",
                },
                {
                    "schema_name": "public",
                    "table_name": "predictions",
                    "column_name": "edge_pct",
                    "data_type": "real",
                },
                {
                    "schema_name": "public",
                    "table_name": "line_snapshots",
                    "column_name": "book_name",
                    "data_type": "varchar",
                },
                {
                    "schema_name": "public",
                    "table_name": "line_snapshots",
                    "column_name": "line_value",
                    "data_type": "real",
                },
                {
                    "schema_name": "public",
                    "table_name": "api_health_log",
                    "column_name": "api_name",
                    "data_type": "varchar",
                },
                {
                    "schema_name": "public",
                    "table_name": "pipeline_runs",
                    "column_name": "dag_name",
                    "data_type": "varchar",
                },
            ]
        if "data_catalog" in sql and "is_phi" in sql:
            return [e for e in self._tables.get("data_catalog", []) if e.get("is_phi")]
        if "data_catalog" in sql:
            return self._tables.get("data_catalog", [])
        if "data_lineage" in sql and "ORDER BY" in sql:
            return self._tables.get("data_lineage", [])
        return []

    def execute_nonquery(self, sql: str, params: tuple = ()) -> int:
        self._query_log.append(sql)
        if "INSERT INTO incidents" in sql:
            new_id = self._next_id("incidents")
            record = {
                "id": new_id,
                "incident_type": params[0] if params else "",
                "severity": params[1] if len(params) > 1 else "warning",
                "status": "detected",
                "title": params[2] if len(params) > 2 else "",
            }
            self._tables["incidents"].append(record)
            return 1
        if "INSERT INTO job_runs" in sql:
            new_id = self._next_id("job_runs")
            self._tables["job_runs"].append(
                {"id": new_id, "job_name": params[0] if params else "", "status": "running"}
            )
            return 1
        if "INSERT INTO validation_results" in sql:
            new_id = self._next_id("validation_results")
            self._tables["validation_results"].append({"id": new_id})
            return 1
        if "INSERT INTO remediation_log" in sql:
            self._tables["remediation_log"].append({"incident_id": params[0] if params else 0})
            return 1
        if "INSERT INTO data_catalog" in sql or "ON CONFLICT" in sql:
            entry = {
                "id": self._next_id("data_catalog"),
                "schema_name": params[0] if params else "public",
                "table_name": params[1] if len(params) > 1 else "",
                "column_name": params[2] if len(params) > 2 else None,
                "is_phi": params[4] if len(params) > 4 else False,
                "is_pii": params[5] if len(params) > 5 else False,
                "phi_category": params[6] if len(params) > 6 else None,
            }
            self._tables["data_catalog"].append(entry)
            return 1
        if "INSERT INTO data_lineage" in sql:
            new_id = self._next_id("data_lineage")
            self._tables["data_lineage"].append(
                {
                    "id": new_id,
                    "pipeline_name": params[0] if params else "",
                    "source_table": params[1] if len(params) > 1 else "",
                    "target_table": params[2] if len(params) > 2 else "",
                    "status": params[3] if len(params) > 3 else "success",
                }
            )
            return 1
        if "INSERT INTO postmortems" in sql:
            self._tables["postmortems"].append({"incident_id": params[0] if params else 0})
            return 1
        if "UPDATE incidents" in sql:
            for inc in self._tables.get("incidents", []):
                if params and inc.get("id") == params[-1]:
                    inc["status"] = params[0]
            return 1
        if "INSERT INTO predictions" in sql:
            new_id = self._next_id("predictions")
            self._tables["predictions"].append({"id": new_id})
            return 1
        if "INSERT INTO pipeline_runs" in sql:
            new_id = self._next_id("pipeline_runs")
            self._tables["pipeline_runs"].append({"id": new_id, "status": "triggered"})
            return 1
        if "INSERT INTO api_health_log" in sql:
            self._tables["api_health_log"].append({"api_name": params[0] if params else ""})
            return 1
        if "INSERT INTO feature_drift_log" in sql:
            self._tables["feature_drift_log"].append({})
            return 1
        if "DELETE FROM" in sql:
            return 5  # Simulate rows affected
        if "UPDATE pick_history" in sql:
            return 3  # Simulate rows affected
        return 0

    def execute_proc(self, proc_name: str, params: tuple = ()) -> list[dict]:
        self._query_log.append(f"SELECT * FROM {proc_name}()")
        if proc_name == "fn_capture_health_snapshot":
            snapshot = {
                "id": self._next_id("health_snapshots"),
                "cpu_percent": 45.0,
                "memory_used_mb": 2048.0,
                "memory_total_mb": 8192.0,
                "connection_count": 25,
                "lock_wait_count": 0,
                "long_query_count": 0,
                "dead_tuple_ratio": 2.5,
                "cache_hit_ratio": 99.1,
                "avg_query_ms": 5.0,
                "status": "healthy",
            }
            self._tables["health_snapshots"].append(snapshot)
            return [snapshot]
        if proc_name == "fn_cleanup_stale_sessions":
            return [{"fn_cleanup_stale_sessions": 0}]
        return []

    def get_connection(self):
        return MagicMock()

    def test_connection(self) -> bool:
        return True

    def _next_id(self, table: str) -> int:
        self._id_counters[table] = self._id_counters.get(table, 0) + 1
        return self._id_counters[table]


@pytest.fixture
def mock_db() -> MockConnectionManager:
    return MockConnectionManager()


@pytest.fixture
def config() -> SentinelConfig:
    return SentinelConfig(
        thresholds=ThresholdConfig(
            cpu_percent_warning=70.0,
            cpu_percent_critical=90.0,
            memory_percent_warning=75.0,
            memory_percent_critical=90.0,
        ),
        validation_rules=[
            ValidationRuleConfig(
                name="test_null_check",
                type="null_check",
                table="predictions",
                column="model_version",
                severity="critical",
                description="Model version must not be NULL",
            ),
            ValidationRuleConfig(
                name="test_range_check",
                type="range_check",
                table="predictions",
                column="p_over",
                severity="warning",
                params={"min": 0, "max": 1},
                description="Probability must be in valid range",
            ),
        ],
    )
