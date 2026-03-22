"""Tests for Performance Room API endpoints."""

from unittest.mock import patch


def _mock_query(rows):
    return patch("sentinel.api.routes.performance._query", return_value=rows)


class TestWinRate:
    def test_empty(self):
        from sentinel.api.routes.performance import get_win_rate

        with _mock_query([]):
            result = get_win_rate(days=7)
        assert result["daily"] == []
        assert result["rolling_win_rate"] == 0
        assert result["total_picks"] == 0

    def test_with_data(self):
        from sentinel.api.routes.performance import get_win_rate

        rows = [
            {"run_date": "2026-03-20", "total": 30, "wins": 18, "win_rate": 60.0},
            {"run_date": "2026-03-21", "total": 25, "wins": 16, "win_rate": 64.0},
        ]

        with _mock_query(rows):
            result = get_win_rate(days=7)

        assert len(result["daily"]) == 2
        assert result["total_picks"] == 55
        assert result["total_wins"] == 34
        assert result["rolling_win_rate"] == round(34 / 55 * 100, 1)

    def test_defaults_to_7_days(self):
        from sentinel.api.routes.performance import get_win_rate

        with _mock_query([]):
            result = get_win_rate(days=7)
        assert result["days"] == 7


class TestConviction:
    def test_empty(self):
        from sentinel.api.routes.performance import get_conviction

        with _mock_query([]):
            result = get_conviction()
        assert result["distribution"] == {"LOCKED": 0, "STRONG": 0, "WATCH": 0, "SKIP": 0}

    def test_with_data(self):
        from sentinel.api.routes.performance import get_conviction

        rows = [
            {"conviction_label": "LOCKED", "count": 3, "avg_conviction": 0.92},
            {"conviction_label": "STRONG", "count": 8, "avg_conviction": 0.75},
            {"conviction_label": "WATCH", "count": 5, "avg_conviction": 0.55},
        ]

        with _mock_query(rows):
            result = get_conviction()

        assert result["distribution"]["LOCKED"] == 3
        assert result["distribution"]["STRONG"] == 8
        assert result["distribution"]["WATCH"] == 5
        assert result["distribution"]["SKIP"] == 0

    def test_unknown_labels_ignored(self):
        from sentinel.api.routes.performance import get_conviction

        rows = [
            {"conviction_label": "LOCKED", "count": 2, "avg_conviction": 0.9},
            {"conviction_label": "CUSTOM", "count": 1, "avg_conviction": 0.5},
        ]

        with _mock_query(rows):
            result = get_conviction()

        assert result["distribution"]["LOCKED"] == 2
        assert "CUSTOM" not in result["distribution"]


class TestSummary:
    def test_empty(self):
        from sentinel.api.routes.performance import get_summary

        with _mock_query([]):
            result = get_summary()
        assert result["last_rollback"] is None
        assert result["volume_14d"] == []
        assert result["props_today"] == 0
        assert result["snapshots_today"] == 0

    def test_with_data(self):
        from sentinel.api.routes.performance import get_summary

        call_count = {"n": 0}

        def _side_effect(sql, params=(), schema="axiom"):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # rollbacks
                return [
                    {
                        "model_version": "v4",
                        "market": "POINTS",
                        "rolled_back_at": "2026-03-20T10:00:00",
                        "rollback_reason": "7d WR 48% < 52%",
                    }
                ]
            elif call_count["n"] == 2:
                # volume
                return [
                    {"run_date": "2026-03-20", "picks": 25},
                    {"run_date": "2026-03-21", "picks": 30},
                ]
            elif call_count["n"] == 3:
                # props today
                return [{"cnt": 500}]
            elif call_count["n"] == 4:
                # snapshots today
                return [{"cnt": 15000}]
            elif call_count["n"] == 5:
                # active models
                return [
                    {
                        "version": "v3_POINTS",
                        "market": "POINTS",
                        "auc": 0.74,
                        "promoted_at": "2026-02-03",
                    }
                ]
            elif call_count["n"] == 6:
                # latest pipeline run
                return [
                    {
                        "run_id": "abc",
                        "status": "success",
                        "summary": {"feature_count": 188},
                        "started_at": "2026-03-22T08:00:00",
                    }
                ]
            return []

        with patch("sentinel.api.routes.performance._query", side_effect=_side_effect):
            result = get_summary()

        assert result["last_rollback"]["model_version"] == "v4"
        assert result["last_rollback"]["rollback_reason"] == "7d WR 48% < 52%"
        assert len(result["volume_14d"]) == 2
        assert result["props_today"] == 500
        assert result["snapshots_today"] == 15000
        assert result["feature_count"] == 188

    def test_summary_json_string_in_run(self):
        import json

        from sentinel.api.routes.performance import get_summary

        call_count = {"n": 0}

        def _side_effect(sql, params=(), schema="axiom"):
            call_count["n"] += 1
            if call_count["n"] == 6:
                return [
                    {
                        "run_id": "x",
                        "status": "success",
                        "summary": json.dumps({"feature_count": 201}),
                        "started_at": None,
                    }
                ]
            if call_count["n"] in (3, 4):
                return [{"cnt": 0}]
            return []

        with patch("sentinel.api.routes.performance._query", side_effect=_side_effect):
            result = get_summary()

        assert result["feature_count"] == 201
