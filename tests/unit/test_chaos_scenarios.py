"""Tests for chaos scenario logic."""

from unittest.mock import MagicMock

from sentinel.chaos.engine import ChaosEngine
from sentinel.chaos.scenarios import (
    BUILTIN_SCENARIOS,
    ConnectionFlood,
    ConvictionCollapse,
    ExtractorDefaultInjection,
    LineIngestionDrop,
)
from sentinel.monitor.incident_manager import IncidentManager


class TestBuiltinScenarios:
    def test_all_scenarios_registered(self):
        assert len(BUILTIN_SCENARIOS) == 9
        assert "Long Running Query" in BUILTIN_SCENARIOS
        assert "Connection Flood" in BUILTIN_SCENARIOS
        assert "DAG Overlap" in BUILTIN_SCENARIOS
        assert "Extractor Default Injection" in BUILTIN_SCENARIOS
        assert "Line Ingestion Drop" in BUILTIN_SCENARIOS
        assert "Model File Missing" in BUILTIN_SCENARIOS
        assert "Conviction Collapse" in BUILTIN_SCENARIOS
        assert "Win Rate Crash" in BUILTIN_SCENARIOS
        assert "Prediction Staleness" in BUILTIN_SCENARIOS

    def test_extractor_default_injection(self, mock_db):
        mock_db.execute_nonquery = MagicMock(return_value=1)
        scenario = ExtractorDefaultInjection()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "feature" in result["detail"].lower() or "0" in result["detail"]

    def test_connection_flood_scenario(self, mock_db):
        scenario = ConnectionFlood()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "connection" in result["detail"].lower() or "opened" in result["detail"].lower()

    def test_conviction_collapse(self, mock_db):
        mock_db.execute_nonquery = MagicMock(return_value=3)
        scenario = ConvictionCollapse()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True

    def test_line_ingestion_drop(self, mock_db):
        mock_db.execute_nonquery = MagicMock(return_value=15000)
        scenario = LineIngestionDrop()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "15000" in result["detail"]


class TestChaosEngine:
    def test_list_scenarios(self, mock_db):
        incidents = IncidentManager(mock_db)
        engine = ChaosEngine(mock_db, incidents)
        scenarios = engine.list_scenarios()
        assert len(scenarios) == 9
        assert all("name" in s for s in scenarios)
        assert all("severity" in s for s in scenarios)

    def test_trigger_known_scenario(self, mock_db):
        incidents = IncidentManager(mock_db)
        engine = ChaosEngine(mock_db, incidents)
        result = engine.trigger("Connection Flood")
        assert result["scenario"] == "Connection Flood"
        assert result.get("triggered") is True

    def test_trigger_unknown_scenario(self, mock_db):
        incidents = IncidentManager(mock_db)
        engine = ChaosEngine(mock_db, incidents)
        result = engine.trigger("Nonexistent")
        assert "error" in result

    def test_cooldown_enforcement(self, mock_db):
        incidents = IncidentManager(mock_db)
        engine = ChaosEngine(mock_db, incidents)
        engine.trigger("Connection Flood")
        result = engine.trigger("Connection Flood")
        assert "cooldown" in result.get("error", "").lower()

    def test_trigger_random(self, mock_db):
        incidents = IncidentManager(mock_db)
        engine = ChaosEngine(mock_db, incidents)
        result = engine.trigger_random()
        assert "scenario" in result
