"""Tests for main.py — monitor loop, lifespan, serve_dashboard."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sentinel.api.dependencies import get_state
from sentinel.api.main import _monitor_loop, app


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


class TestServeDashboard:
    def test_root_serves_dashboard_or_fallback(self, client):
        """GET / returns either the HTML file or the JSON fallback."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.text
        assert "Sentinel" in data or "Sport-Suite" in data or "html" in data.lower()

    def test_root_fallback_when_no_template(self, client):
        """GET / returns JSON message when index.html is missing."""
        with patch("sentinel.api.main.os.path.exists", return_value=False):
            resp = client.get("/")
            assert resp.status_code == 200
            data = resp.json()
            assert data["message"] == "Sport-Suite Sentinel API"
            assert data["docs"] == "/docs"


class TestMonitorLoop:
    @pytest.mark.asyncio
    async def test_monitor_loop_processes_alerts(self):
        """Monitor loop collects snapshots and creates incidents for critical."""
        state = MagicMock()
        state.config.monitor.poll_interval_seconds = 0.01
        state.config.monitor.auto_remediate = False
        state.config.monitor.escalation_timeout_seconds = 300

        state.health.collect_snapshot.return_value = {
            "alerts": [
                {
                    "metric": "cpu_percent",
                    "level": "critical",
                    "value": 95.0,
                    "threshold": 90.0,
                }
            ]
        }
        state.pipeline.collect_metrics.return_value = {}
        state.pipeline.evaluate_thresholds.return_value = []
        state.incidents.check_escalations.return_value = []

        task = asyncio.create_task(_monitor_loop(state))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        state.health.collect_snapshot.assert_called()
        state.incidents.create.assert_called()
        call_kwargs = state.incidents.create.call_args
        assert "cpu_percent" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_monitor_loop_auto_remediates(self):
        """Monitor loop calls remediate when auto_remediate is True."""
        state = MagicMock()
        state.config.monitor.poll_interval_seconds = 0.01
        state.config.monitor.auto_remediate = True
        state.config.monitor.escalation_timeout_seconds = 300
        state.health.collect_snapshot.return_value = {"alerts": []}
        state.pipeline.collect_metrics.return_value = {}
        state.pipeline.evaluate_thresholds.return_value = []
        state.incidents.check_escalations.return_value = []

        task = asyncio.create_task(_monitor_loop(state))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        state.remediation.remediate_open_incidents.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_loop_handles_pipeline_error(self):
        """Monitor loop survives pipeline metrics failure."""
        state = MagicMock()
        state.config.monitor.poll_interval_seconds = 0.01
        state.config.monitor.auto_remediate = False
        state.config.monitor.escalation_timeout_seconds = 300
        state.health.collect_snapshot.return_value = {"alerts": []}
        state.pipeline.collect_metrics.side_effect = Exception("DB down")
        state.incidents.check_escalations.return_value = []

        task = asyncio.create_task(_monitor_loop(state))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Loop survived the exception
        assert state.health.collect_snapshot.call_count >= 1

    @pytest.mark.asyncio
    async def test_monitor_loop_handles_critical_error(self):
        """Monitor loop survives even if collect_snapshot raises."""
        state = MagicMock()
        state.config.monitor.poll_interval_seconds = 0.01
        state.config.monitor.auto_remediate = False
        state.health.collect_snapshot.side_effect = Exception("Total failure")

        task = asyncio.create_task(_monitor_loop(state))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert state.health.collect_snapshot.call_count >= 1

    @pytest.mark.asyncio
    async def test_monitor_loop_pipeline_critical_creates_incident(self):
        """Pipeline critical alerts create incidents."""
        state = MagicMock()
        state.config.monitor.poll_interval_seconds = 0.01
        state.config.monitor.auto_remediate = False
        state.config.monitor.escalation_timeout_seconds = 300
        state.health.collect_snapshot.return_value = {"alerts": []}
        state.pipeline.collect_metrics.return_value = {"win_rate_7d": 48.0}
        state.pipeline.evaluate_thresholds.return_value = [
            {
                "metric": "win_rate_7d",
                "level": "critical",
                "value": 48.0,
                "threshold": 50.0,
            }
        ]
        state.incidents.check_escalations.return_value = []

        task = asyncio.create_task(_monitor_loop(state))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        state.incidents.create.assert_called()
        call_kwargs = state.incidents.create.call_args
        assert "win_rate_7d" in str(call_kwargs)
