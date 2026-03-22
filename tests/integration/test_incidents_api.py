"""Integration tests for incident API routes — covers SLA, remediation, postmortems."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from sentinel.api.dependencies import get_state
from sentinel.api.main import app


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class MockAppState:
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
    original = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c
    app.router.lifespan_context = original
    app.dependency_overrides.clear()


class TestOpenIncidents:
    def test_list_open_incidents(self, client):
        resp = client.get("/api/incidents/open")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestPostmortemsAPI:
    def test_list_postmortems(self, client):
        resp = client.get("/api/incidents/postmortems/recent")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_postmortem_not_found(self, client):
        resp = client.get("/api/incidents/9999/postmortem")
        assert resp.status_code == 404


class TestSlaMetrics:
    def test_sla_no_incidents(self, client):
        """SLA endpoint returns zero totals when no incidents exist."""
        resp = client.get("/api/incidents/metrics/sla")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_incidents"] == 0
        assert data["window_hours"] == 24

    def test_sla_with_incidents(self, client, mock_db):
        """SLA endpoint computes metrics when incidents exist."""
        now = datetime.utcnow()
        mock_db._tables["incidents"] = [
            {
                "id": 1,
                "incident_type": "cpu",
                "severity": "critical",
                "status": "resolved",
                "title": "High CPU",
                "detected_at": now - timedelta(hours=1),
                "resolved_at": now - timedelta(minutes=30),
                "resolved_by": "auto",
            },
            {
                "id": 2,
                "incident_type": "memory",
                "severity": "warning",
                "status": "escalated",
                "title": "High Memory",
                "detected_at": now - timedelta(hours=2),
                "resolved_at": now - timedelta(hours=1),
                "resolved_by": "manual",
            },
            {
                "id": 3,
                "incident_type": "blocking",
                "severity": "warning",
                "status": "detected",
                "title": "Blocking chain",
                "detected_at": now - timedelta(minutes=10),
                "resolved_at": None,
                "resolved_by": None,
            },
        ]
        resp = client.get("/api/incidents/metrics/sla?hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_incidents"] == 3
        assert data["resolved_count"] == 2
        assert data["escalated_count"] == 1
        assert data["critical_count"] == 1
        assert data["auto_resolved_count"] == 1
        assert data["avg_resolution_minutes"] is not None

    def test_sla_custom_window(self, client):
        resp = client.get("/api/incidents/metrics/sla?hours=1")
        assert resp.status_code == 200
        assert resp.json()["window_hours"] == 1


class TestUpdateIncident:
    def test_update_status(self, client):
        """Create then update an incident."""
        # Create
        resp = client.post(
            "/api/incidents",
            json={"incident_type": "test", "title": "Update test", "severity": "warning"},
        )
        assert resp.status_code == 200
        inc_id = resp.json()["id"]

        # Update to investigating
        resp = client.patch(
            f"/api/incidents/{inc_id}",
            json={"status": "investigating"},
        )
        assert resp.status_code == 200

    def test_update_invalid_status(self, client):
        """Invalid status returns 400."""
        resp = client.post(
            "/api/incidents",
            json={"incident_type": "test", "title": "Bad update", "severity": "warning"},
        )
        inc_id = resp.json()["id"]

        resp = client.patch(
            f"/api/incidents/{inc_id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422  # Pydantic validation


class TestRemediateIncident:
    def test_remediate_not_found(self, client):
        resp = client.post("/api/incidents/9999/remediate")
        assert resp.status_code == 404

    def test_remediate_existing(self, client):
        """Create an incident, then try to remediate."""
        resp = client.post(
            "/api/incidents",
            json={
                "incident_type": "blocking",
                "title": "Block test",
                "severity": "warning",
            },
        )
        assert resp.status_code == 200
        inc_id = resp.json()["id"]

        resp = client.post(f"/api/incidents/{inc_id}/remediate")
        assert resp.status_code == 200
        data = resp.json()
        assert "remediated" in data


class TestGetIncident:
    def test_get_existing(self, client):
        resp = client.post(
            "/api/incidents",
            json={"incident_type": "test", "title": "Get test", "severity": "info"},
        )
        inc_id = resp.json()["id"]

        resp = client.get(f"/api/incidents/{inc_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == inc_id

    def test_get_not_found(self, client):
        resp = client.get("/api/incidents/99999")
        assert resp.status_code == 404
