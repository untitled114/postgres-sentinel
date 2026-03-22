"""Tests for RemediationEngine — pattern matching, execution, and escalation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sentinel.core.exceptions import DatabaseQueryError
from sentinel.monitor.incident_manager import IncidentManager
from sentinel.remediation.engine import RemediationEngine


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_incidents(mock_db):
    im = IncidentManager(mock_db)
    im.update_status = MagicMock(return_value={"id": 1, "status": "resolved"})
    im.list_open = MagicMock(return_value=[])
    return im


@pytest.fixture
def engine(mock_db, mock_incidents):
    return RemediationEngine(mock_db, mock_incidents)


class TestAttemptRemediation:
    def test_no_matching_pattern(self, engine):
        incident = {"id": 1, "incident_type": "unknown_type", "status": "detected"}
        result = engine.attempt_remediation(incident)
        assert result["remediated"] is False
        assert "No matching pattern" in result["reason"]

    def test_cpu_pattern_matches(self, engine, mock_db):
        mock_db.execute_proc.return_value = [{"sessions_killed": 2}]
        mock_db.execute_nonquery.return_value = 1
        incident = {"id": 1, "incident_type": "cpu", "status": "detected"}
        result = engine.attempt_remediation(incident)
        assert result["remediated"] is True
        assert result["action"] == "cleanup_stale_sessions"

    def test_action_failure_escalates(self, engine, mock_db):
        mock_db.execute_proc.side_effect = DatabaseQueryError("connection lost")
        mock_db.execute_nonquery.return_value = 1
        incident = {"id": 1, "incident_type": "cpu", "status": "detected"}
        result = engine.attempt_remediation(incident)
        assert result["remediated"] is False
        assert result.get("escalated") is True

    def test_chaos_prediction_stale_pattern(self, engine, mock_db):
        mock_db.execute_nonquery.return_value = 1
        incident = {"id": 2, "incident_type": "chaos:prediction_stale", "status": "detected"}
        result = engine.attempt_remediation(incident)
        assert result["remediated"] is True
        assert result["action"] == "trigger_pipeline_refresh"

    def test_status_transitions(self, engine, mock_db, mock_incidents):
        mock_db.execute_proc.return_value = [{"sessions_killed": 0}]
        mock_db.execute_nonquery.return_value = 1
        incident = {"id": 5, "incident_type": "cpu", "status": "detected"}
        engine.attempt_remediation(incident)

        # Should transition to remediating, then resolved
        calls = mock_incidents.update_status.call_args_list
        assert calls[0].args == (5, "remediating")
        assert calls[1].args == (5, "resolved")


class TestRemediateOpenIncidents:
    def test_no_open_incidents(self, engine, mock_incidents):
        mock_incidents.list_open.return_value = []
        results = engine.remediate_open_incidents()
        assert results == []

    def test_filters_by_status(self, engine, mock_incidents, mock_db):
        mock_incidents.list_open.return_value = [
            {"id": 1, "incident_type": "cpu", "status": "detected"},
            {"id": 2, "incident_type": "cpu", "status": "remediating"},
            {"id": 3, "incident_type": "cpu", "status": "investigating"},
        ]
        mock_db.execute_proc.return_value = [{"sessions_killed": 0}]
        mock_db.execute_nonquery.return_value = 1
        results = engine.remediate_open_incidents()
        # Only detected + investigating should be attempted (not remediating)
        assert len(results) == 2
        attempted_ids = {r["incident_id"] for r in results}
        assert attempted_ids == {1, 3}


class TestRemediationLogging:
    def test_log_success(self, engine, mock_db):
        mock_db.execute_proc.return_value = [{"sessions_killed": 0}]
        mock_db.execute_nonquery.return_value = 1
        incident = {"id": 1, "incident_type": "cpu", "status": "detected"}
        engine.attempt_remediation(incident)

        # Check that INSERT INTO remediation_log was called
        log_calls = [
            c for c in mock_db.execute_nonquery.call_args_list if "remediation_log" in str(c)
        ]
        assert len(log_calls) == 1

    def test_log_db_error_does_not_crash(self, engine, mock_db):
        mock_db.execute_proc.return_value = [{"sessions_killed": 0}]
        # First nonquery call succeeds (remediation_log), but make _log write fail

        def selective_fail(sql, params=()):
            if "remediation_log" in sql:
                raise DatabaseQueryError("disk full")
            return 1

        mock_db.execute_nonquery = MagicMock(side_effect=selective_fail)
        incident = {"id": 1, "incident_type": "cpu", "status": "detected"}
        # Should not raise
        result = engine.attempt_remediation(incident)
        assert result["remediated"] is True
