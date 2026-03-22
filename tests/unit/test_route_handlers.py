"""Tests for chaos, jobs, validation, and dashboard route handlers — covering edge cases."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from sentinel.api.dependencies import get_state
from sentinel.api.main import app


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class MockAppState:
    """Configurable mock state for route handler tests."""

    def __init__(self):
        self.chaos = MagicMock()
        self.jobs = MagicMock()
        self.validation = MagicMock()
        self.health = MagicMock()
        self.incidents = MagicMock()
        self.catalog = MagicMock()
        self.pipeline = MagicMock()
        self.config = MagicMock()


@pytest.fixture
def state():
    return MockAppState()


@pytest.fixture
def client(state):
    app.dependency_overrides[get_state] = lambda: state
    original = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c
    app.router.lifespan_context = original
    app.dependency_overrides.clear()


# --- Chaos routes (lines 22-27) ---


class TestChaosRoutes:
    def test_trigger_unknown_scenario_returns_404(self, client, state):
        state.chaos.trigger.return_value = {"error": "Unknown scenario: FakeScenario"}
        resp = client.post("/api/chaos/trigger", json={"scenario": "FakeScenario"})
        assert resp.status_code == 404
        assert "Unknown scenario" in resp.json()["detail"]

    def test_trigger_cooldown_returns_429(self, client, state):
        state.chaos.trigger.return_value = {"error": "On cooldown — retry in 25s"}
        resp = client.post("/api/chaos/trigger", json={"scenario": "Connection Flood"})
        assert resp.status_code == 429
        assert "cooldown" in resp.json()["detail"].lower()

    def test_trigger_success(self, client, state):
        state.chaos.trigger.return_value = {
            "scenario": "Connection Flood",
            "triggered": True,
            "detail": "Opened 50 idle connections",
        }
        resp = client.post("/api/chaos/trigger", json={"scenario": "Connection Flood"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["triggered"] is True
        assert data["scenario"] == "Connection Flood"

    def test_trigger_random_delegates_to_engine(self, client, state):
        state.chaos.trigger_random.return_value = {
            "scenario": "DAG Overlap",
            "triggered": True,
            "detail": "Injected overlap",
        }
        resp = client.post("/api/chaos/random")
        assert resp.status_code == 200
        assert resp.json()["scenario"] == "DAG Overlap"

    def test_list_scenarios_delegates(self, client, state):
        state.chaos.list_scenarios.return_value = [
            {"name": "Connection Flood", "description": "desc", "severity": "high"}
        ]
        resp = client.get("/api/chaos")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# --- Jobs routes (lines 26, 32-35) ---


class TestJobsRoutes:
    def test_job_history(self, client, state):
        state.jobs.get_history.return_value = [{"job_name": "cleanup", "status": "success"}]
        resp = client.get("/api/jobs/history?job_name=cleanup&limit=5")
        assert resp.status_code == 200
        state.jobs.get_history.assert_called_once_with(job_name="cleanup", limit=5)

    def test_job_history_default_params(self, client, state):
        state.jobs.get_history.return_value = []
        resp = client.get("/api/jobs/history")
        assert resp.status_code == 200
        state.jobs.get_history.assert_called_once_with(job_name=None, limit=20)

    def test_trigger_job_success(self, client, state):
        state.jobs.run_job.return_value = {
            "job_name": "cleanup",
            "status": "success",
            "rows_affected": 5,
            "duration_ms": 120,
        }
        resp = client.post("/api/jobs/trigger", json={"job_name": "cleanup"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["rows_affected"] == 5

    def test_trigger_job_not_found(self, client, state):
        state.jobs.run_job.return_value = {"error": "Job 'nonexistent' not found"}
        resp = client.post("/api/jobs/trigger", json={"job_name": "nonexistent"})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_list_jobs(self, client, state):
        state.jobs.get_all_jobs.return_value = [
            {"name": "cleanup", "schedule": "*/5 * * * *", "interval_seconds": 300, "enabled": True}
        ]
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# --- Validation routes (lines 22, 28-30) ---


class TestValidationRoutes:
    def test_get_results(self, client, state):
        state.validation.get_recent_results.return_value = [
            {"rule_name": "null_check", "passed": True}
        ]
        resp = client.get("/api/validation/results?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        state.validation.get_recent_results.assert_called_once_with(limit=10)

    def test_get_results_default_limit(self, client, state):
        state.validation.get_recent_results.return_value = []
        resp = client.get("/api/validation/results")
        assert resp.status_code == 200
        state.validation.get_recent_results.assert_called_once_with(limit=50)

    def test_run_validation(self, client, state):
        state.validation.run_all.return_value = [
            {"rule_name": "null_check", "passed": True},
            {"rule_name": "range_check", "passed": False},
            {"rule_name": "freshness", "passed": True},
        ]
        resp = client.post("/api/validation/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["passed"] == 2
        assert data["failed"] == 1

    def test_run_validation_all_pass(self, client, state):
        state.validation.run_all.return_value = [
            {"rule_name": "r1", "passed": True},
            {"rule_name": "r2", "passed": True},
        ]
        resp = client.post("/api/validation/run")
        data = resp.json()
        assert data["passed"] == 2
        assert data["failed"] == 0

    def test_run_validation_empty(self, client, state):
        state.validation.run_all.return_value = []
        resp = client.post("/api/validation/run")
        data = resp.json()
        assert data["total"] == 0
        assert data["passed"] == 0
        assert data["failed"] == 0

    def test_get_scorecard(self, client, state):
        state.validation.get_scorecard.return_value = {
            "total_rules": 5,
            "passed": 4,
            "failed": 1,
            "critical_failures": 0,
            "score_percent": 80.0,
            "rules": [],
        }
        resp = client.get("/api/validation/scorecard")
        assert resp.status_code == 200
        assert resp.json()["score_percent"] == 80.0


# --- Dashboard route (lines 40-41) ---


class TestDashboardRoute:
    def test_dashboard_pipeline_fallback_on_error(self, client, state):
        """When pipeline.collect_metrics raises, falls back to get_latest_metrics."""
        state.health.get_latest.return_value = {"status": "healthy"}
        state.incidents.list_open.return_value = []
        state.incidents.list_recent.return_value = []
        state.jobs.get_all_jobs.return_value = []
        state.jobs.get_history.return_value = []
        state.validation.get_scorecard.return_value = {
            "total_rules": 0,
            "passed": 0,
            "failed": 0,
            "critical_failures": 0,
            "score_percent": 100.0,
            "rules": [],
        }
        state.chaos.list_scenarios.return_value = []
        state.incidents.list_postmortems.return_value = []

        state.pipeline.collect_metrics.side_effect = Exception("DB down")
        state.pipeline.get_latest_metrics.return_value = {"win_rate_7d": 55.0}

        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline"] == {"win_rate_7d": 55.0}
        state.pipeline.get_latest_metrics.assert_called_once()


# --- Governance routes (lines 59-69) ---


class TestGovernanceRecordLineage:
    def test_record_lineage(self, client, state):
        state.catalog.record_lineage.return_value = 42
        resp = client.post(
            "/api/governance/lineage",
            json={
                "pipeline_name": "nba_full_pipeline",
                "source_table": "nba_props_xl",
                "target_table": "nba_prediction_history",
                "rows_read": 500,
                "rows_written": 480,
                "rows_rejected": 20,
                "status": "success",
                "error_message": None,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 42
        assert data["status"] == "recorded"
        state.catalog.record_lineage.assert_called_once_with(
            pipeline_name="nba_full_pipeline",
            source_table="nba_props_xl",
            target_table="nba_prediction_history",
            rows_read=500,
            rows_written=480,
            rows_rejected=20,
            status="success",
            error_message=None,
        )

    def test_record_lineage_with_error(self, client, state):
        state.catalog.record_lineage.return_value = 99
        resp = client.post(
            "/api/governance/lineage",
            json={
                "pipeline_name": "broken_pipe",
                "source_table": "src",
                "target_table": "tgt",
                "status": "failed",
                "error_message": "connection timeout",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == 99
