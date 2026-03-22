"""Integration tests for API endpoints using TestClient."""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from sentinel.api.dependencies import get_state
from sentinel.api.main import app


@asynccontextmanager
async def _noop_lifespan(app):
    """Disable background tasks (monitor loop, job runner) during tests."""
    yield


class MockAppState:
    """Minimal mock of AppState for API testing."""

    def __init__(self, mock_db, config):
        from sentinel.chaos.engine import ChaosEngine
        from sentinel.governance.catalog import DataCatalogEngine
        from sentinel.jobs.runner import JobRunner
        from sentinel.monitor.blocker_detector import BlockerDetector
        from sentinel.monitor.health import HealthCollector
        from sentinel.monitor.incident_manager import IncidentManager
        from sentinel.monitor.pipeline import PipelineMonitor
        from sentinel.remediation.engine import RemediationEngine
        from sentinel.validation.engine import ValidationEngine

        self.config = config
        self.db = mock_db
        self.health = HealthCollector(mock_db, config)
        self.blocker = BlockerDetector(mock_db)
        self.incidents = IncidentManager(mock_db)
        self.validation = ValidationEngine(mock_db, config.validation_rules)
        self.jobs = JobRunner(mock_db, config.jobs)
        self.chaos = ChaosEngine(mock_db, self.incidents)
        self.remediation = RemediationEngine(mock_db, self.incidents)
        self.catalog = DataCatalogEngine(mock_db)
        self.pipeline = PipelineMonitor(mock_db, config.thresholds)


@pytest.fixture
def client(mock_db, config):
    state = MockAppState(mock_db, config)
    app.dependency_overrides[get_state] = lambda: state
    # Replace lifespan to skip SQL Server connection + background tasks
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


class TestHealthAPI:
    def test_get_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "sql_connected" in data

    def test_get_sql_health(self, client):
        resp = client.get("/api/health/sql")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True

    def test_capture_snapshot(self, client):
        resp = client.post("/api/health/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestIncidentsAPI:
    def test_list_incidents(self, client):
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_incident(self, client):
        resp = client.post(
            "/api/incidents",
            json={
                "incident_type": "test",
                "title": "API test incident",
                "severity": "warning",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "detected"

    def test_get_incident_not_found(self, client):
        resp = client.get("/api/incidents/9999")
        assert resp.status_code == 404


class TestJobsAPI:
    def test_list_jobs(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestValidationAPI:
    def test_get_scorecard(self, client):
        resp = client.get("/api/validation/scorecard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_rules" in data
        assert "score_percent" in data


class TestChaosAPI:
    def test_list_scenarios(self, client):
        resp = client.get("/api/chaos")
        assert resp.status_code == 200
        scenarios = resp.json()
        assert len(scenarios) == 9

    def test_trigger_random(self, client):
        resp = client.post("/api/chaos/random")
        assert resp.status_code == 200
        assert "scenario" in resp.json()


class TestDashboardAPI:
    def test_get_dashboard(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "health" in data
        assert "open_incidents" in data
        assert "jobs" in data
        assert "validation" in data
        assert "chaos_scenarios" in data
        assert "postmortems" in data
