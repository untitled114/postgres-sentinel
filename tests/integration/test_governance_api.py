"""Integration tests for governance API endpoints."""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from sentinel.api.dependencies import get_state
from sentinel.api.main import app
from sentinel.governance.catalog import DataCatalogEngine


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class MockAppState:
    """Mock AppState with governance catalog engine."""

    def __init__(self, mock_db, config):
        from sentinel.chaos.engine import ChaosEngine
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
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


class TestGovernanceCatalogAPI:
    def test_get_catalog(self, client):
        resp = client.get("/api/governance/catalog")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_sensitive_columns(self, client):
        resp = client.get("/api/governance/catalog/sensitive")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_scan_schema(self, client):
        resp = client.post("/api/governance/catalog/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert "columns_scanned" in data
        assert "phi_pii_classified" in data
        assert data["columns_scanned"] == 8

    def test_scan_schema_custom(self, client):
        resp = client.post("/api/governance/catalog/scan?schema_name=public")
        assert resp.status_code == 200

    def test_get_catalog_filtered_by_table(self, client):
        resp = client.get("/api/governance/catalog?table=predictions")
        assert resp.status_code == 200


class TestGovernanceLineageAPI:
    def test_get_lineage(self, client):
        resp = client.get("/api/governance/lineage")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_lineage_filtered(self, client):
        resp = client.get("/api/governance/lineage?pipeline=claim_ingestion")
        assert resp.status_code == 200

    def test_get_lineage_with_limit(self, client):
        resp = client.get("/api/governance/lineage?limit=10")
        assert resp.status_code == 200
