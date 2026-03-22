"""Tests for Training Room API endpoints."""

from unittest.mock import patch


def _mock_query(rows):
    """Patch _query in training module to return fixed rows."""
    return patch("sentinel.api.routes.training._query", return_value=rows)


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
        assert result["registry"] == []
        assert result["timeline"] == []

    def test_with_data(self):
        from sentinel.api.routes.training import get_registry

        registry_rows = [
            {
                "market": "POINTS",
                "production_version": "v3",
                "promoted_at": "2026-02-03",
                "previous_version": "xl",
                "rollback_count": 0,
            }
        ]
        timeline_rows = [
            {
                "model_version": "v3",
                "market": "POINTS",
                "run_date": "2026-02-03",
                "auc_mean": 0.74,
                "wr_mean": 0.60,
                "promoted": True,
                "promoted_at": "2026-02-03",
                "rolled_back": False,
                "rolled_back_at": None,
                "rollback_reason": None,
            }
        ]

        call_count = {"n": 0}

        def _side_effect(sql, params=()):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return registry_rows
            return timeline_rows

        with patch("sentinel.api.routes.training._query", side_effect=_side_effect):
            result = get_registry()

        assert len(result["registry"]) == 1
        assert result["registry"][0]["production_version"] == "v3"
