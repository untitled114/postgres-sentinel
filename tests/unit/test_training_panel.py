"""Tests for Training Room API endpoints."""

from unittest.mock import MagicMock, patch

import psycopg2


def _mock_query(rows):
    """Patch _query in training module to return fixed rows."""
    return patch("sentinel.api.routes.training._query", return_value=rows)


class TestGetConn:
    def test_get_conn_calls_psycopg2_connect(self):
        from sentinel.api.routes.training import _get_conn

        mock_conn = MagicMock()
        mock_cfg = MagicMock()
        mock_cfg.host = "localhost"
        mock_cfg.port = 5541
        mock_cfg.name = "cephalon_axiom"
        mock_cfg.user = "sentinel"
        mock_cfg.password = "pass"
        mock_cfg.connect_timeout = 10

        mock_sentinel_cfg = MagicMock()
        mock_sentinel_cfg.database = mock_cfg

        with (
            patch("sentinel.api.routes.training.load_config", return_value=mock_sentinel_cfg),
            patch(
                "sentinel.api.routes.training.psycopg2.connect", return_value=mock_conn
            ) as mock_connect,
        ):
            conn = _get_conn()

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5541,
            dbname="cephalon_axiom",
            user="sentinel",
            password="pass",
            options="-c search_path=axiom,public",
            connect_timeout=10,
        )
        assert conn.autocommit is True

    def test_get_conn_propagates_connect_error(self):
        from sentinel.api.routes.training import _get_conn

        mock_cfg = MagicMock()
        mock_sentinel_cfg = MagicMock()
        mock_sentinel_cfg.database = mock_cfg

        with (
            patch("sentinel.api.routes.training.load_config", return_value=mock_sentinel_cfg),
            patch(
                "sentinel.api.routes.training.psycopg2.connect",
                side_effect=psycopg2.OperationalError("connection refused"),
            ),
        ):
            import pytest

            with pytest.raises(psycopg2.OperationalError):
                _get_conn()


class TestQueryHelper:
    def test_query_returns_rows_on_success(self):
        from sentinel.api.routes.training import _query

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("sentinel.api.routes.training._get_conn", return_value=mock_conn):
            result = _query("SELECT * FROM pipeline_runs")

        assert result == [{"id": 1, "name": "test"}]
        mock_conn.close.assert_called_once()

    def test_query_returns_empty_on_exception(self):
        from sentinel.api.routes.training import _query

        with patch(
            "sentinel.api.routes.training._get_conn",
            side_effect=Exception("DB down"),
        ):
            result = _query("SELECT 1")

        assert result == []

    def test_query_passes_params(self):
        from sentinel.api.routes.training import _query

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("sentinel.api.routes.training._get_conn", return_value=mock_conn):
            _query("SELECT * FROM t WHERE id = %s", (42,))

        mock_cursor.execute.assert_called_once_with("SELECT * FROM t WHERE id = %s", (42,))


class TestLatestTraining:
    def test_no_runs(self):
        from sentinel.api.routes.training import get_latest_training

        with _mock_query([]):
            result = get_latest_training()
        assert result["run"] is None
        assert result["extractors"] == []

    def test_with_run_and_tasks(self):
        from sentinel.api.routes.training import get_latest_training

        run = {
            "run_id": "abc-123",
            "run_date": "2026-03-22",
            "run_type": "training",
            "started_at": "2026-03-22T08:00:00",
            "ended_at": "2026-03-22T08:30:00",
            "status": "success",
            "duration_ms": 1800000,
            "tasks": [
                {
                    "name": "extract_bp_analytics",
                    "status": "success",
                    "duration_ms": 5000,
                    "metrics": {"feature_count": 15, "default_rate": 0.05},
                },
                {
                    "name": "extract_game_context",
                    "status": "success",
                    "duration_ms": 3000,
                    "metrics": {"feature_count": 8},
                },
            ],
            "summary": {"feature_count": 188},
        }

        with _mock_query([run]):
            result = get_latest_training()

        assert result["run"]["run_id"] == "abc-123"
        assert len(result["extractors"]) == 2
        assert result["extractors"][0]["name"] == "extract_bp_analytics"
        assert result["extractors"][0]["metrics"]["feature_count"] == 15

    def test_tasks_as_json_string(self):
        import json

        from sentinel.api.routes.training import get_latest_training

        run = {
            "run_id": "def-456",
            "run_date": "2026-03-22",
            "run_type": "training",
            "started_at": None,
            "ended_at": None,
            "status": "success",
            "duration_ms": None,
            "tasks": json.dumps(
                [{"name": "train_lgbm", "status": "success", "metrics": {"auc": 0.78}}]
            ),
            "summary": {},
        }

        with _mock_query([run]):
            result = get_latest_training()

        assert len(result["extractors"]) == 1

    def test_tasks_without_metrics_skipped(self):
        from sentinel.api.routes.training import get_latest_training

        run = {
            "run_id": "x",
            "run_date": "2026-03-22",
            "run_type": "training",
            "started_at": None,
            "ended_at": None,
            "status": "success",
            "duration_ms": None,
            "tasks": [
                {"name": "no_metrics_task", "status": "success"},
                {"name": "with_metrics", "status": "success", "metrics": {"count": 5}},
            ],
            "summary": {},
        }

        with _mock_query([run]):
            result = get_latest_training()

        assert len(result["extractors"]) == 1
        assert result["extractors"][0]["name"] == "with_metrics"


class TestValidations:
    def test_empty(self):
        from sentinel.api.routes.training import get_validations

        with _mock_query([]):
            result = get_validations()
        assert result["validations"] == []

    def test_with_rows(self):
        from sentinel.api.routes.training import get_validations

        rows = [
            {
                "id": 1,
                "model_version": "v4",
                "market": "POINTS",
                "run_date": "2026-03-22",
                "auc_mean": 0.78,
                "auc_std": 0.02,
                "wr_mean": 0.65,
                "roi_mean": 0.12,
                "fold_count": 6,
                "beats_baseline": True,
                "promoted": False,
                "rolled_back": False,
                "rollback_reason": None,
            }
        ]

        with _mock_query(rows):
            result = get_validations()

        assert len(result["validations"]) == 1
        assert result["validations"][0]["auc_mean"] == 0.78


class TestRegistry:
    def test_empty(self):
        from sentinel.api.routes.training import get_registry

        with _mock_query([]):
            result = get_registry()
        assert result["models"] == []

    def test_with_data(self):
        from sentinel.api.routes.training import get_registry

        rows = [
            {
                "version": "v3_POINTS_20260203",
                "market": "POINTS",
                "status": "production",
                "auc": 0.740,
                "r2": 0.548,
                "feature_count": 136,
                "pkl_path": "nba/models/saved_xl/points_v3_*.pkl",
                "promoted_at": "2026-02-03",
                "rolled_back_at": None,
                "created_at": "2026-02-03",
            }
        ]

        with _mock_query(rows):
            result = get_registry()

        assert len(result["models"]) == 1
        assert result["models"][0]["version"] == "v3_POINTS_20260203"
        assert result["models"][0]["status"] == "production"
