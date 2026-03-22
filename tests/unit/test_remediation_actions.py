"""Tests for remediation actions — individual action functions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sentinel.core.exceptions import DatabaseQueryError
from sentinel.remediation.actions import (
    ACTIONS,
    cleanup_stale_sessions,
    kill_blocking_session,
    restart_failed_job,
    trigger_line_refresh,
    trigger_pipeline_refresh,
)


@pytest.fixture
def mock_db():
    return MagicMock()


class TestKillBlockingSession:
    def test_success(self, mock_db):
        mock_db.execute_query.return_value = []
        result = kill_blocking_session(mock_db, session_id=55)
        assert result["success"] is True
        assert "55" in result["detail"]

    def test_failure(self, mock_db):
        mock_db.execute_query.side_effect = DatabaseQueryError("cannot kill system session")
        result = kill_blocking_session(mock_db, session_id=1)
        assert result["success"] is False


class TestCleanupStaleSessions:
    def test_success(self, mock_db):
        mock_db.execute_proc.return_value = [{"sessions_killed": 3}]
        result = cleanup_stale_sessions(mock_db, idle_minutes=30)
        assert result["success"] is True
        assert "3" in result["detail"]

    def test_failure(self, mock_db):
        mock_db.execute_proc.side_effect = DatabaseQueryError("permission denied")
        result = cleanup_stale_sessions(mock_db, idle_minutes=30)
        assert result["success"] is False


class TestRestartFailedJob:
    def test_success(self, mock_db):
        mock_db.execute_nonquery.return_value = 1
        result = restart_failed_job(mock_db, job_name="etl_daily")
        assert result["success"] is True
        assert "etl_daily" in result["detail"]

    def test_failure(self, mock_db):
        mock_db.execute_nonquery.side_effect = DatabaseQueryError("table locked")
        result = restart_failed_job(mock_db, job_name="etl_daily")
        assert result["success"] is False


class TestTriggerPipelineRefresh:
    def test_success(self, mock_db):
        mock_db.execute_nonquery.return_value = 1
        result = trigger_pipeline_refresh(mock_db)
        assert result["success"] is True

    def test_failure(self, mock_db):
        mock_db.execute_nonquery.side_effect = DatabaseQueryError("err")
        result = trigger_pipeline_refresh(mock_db)
        assert result["success"] is False


class TestTriggerLineRefresh:
    def test_success(self, mock_db):
        mock_db.execute_nonquery.return_value = 1
        result = trigger_line_refresh(mock_db)
        assert result["success"] is True

    def test_failure(self, mock_db):
        mock_db.execute_nonquery.side_effect = DatabaseQueryError("err")
        result = trigger_line_refresh(mock_db)
        assert result["success"] is False


class TestActionsRegistry:
    def test_all_actions_registered(self):
        expected = {
            "kill_blocking_session",
            "cleanup_stale_sessions",
            "restart_failed_job",
            "escalate_to_manual",
            "trigger_pipeline_refresh",
            "trigger_line_refresh",
        }
        assert set(ACTIONS.keys()) == expected

    def test_all_actions_callable(self):
        for name, fn in ACTIONS.items():
            assert callable(fn), f"Action '{name}' is not callable"
