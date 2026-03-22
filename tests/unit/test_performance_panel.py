"""Tests for Performance Room API endpoints."""

from unittest.mock import MagicMock, patch


def _mock_query(rows):
    return patch("sentinel.api.routes.performance._query", return_value=rows)


class TestPerfGetConn:
    def test_get_conn_calls_psycopg2_connect_with_schema(self):
        from sentinel.api.routes.performance import _get_conn

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
            patch("sentinel.api.routes.performance.load_config", return_value=mock_sentinel_cfg),
            patch(
                "sentinel.api.routes.performance.psycopg2.connect", return_value=mock_conn
            ) as mock_connect,
        ):
            conn = _get_conn(schema="intelligence")

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5541,
            dbname="cephalon_axiom",
            user="sentinel",
            password="pass",
            options="-c search_path=intelligence,public",
            connect_timeout=10,
        )
        assert conn.autocommit is True

    def test_get_conn_default_schema_is_axiom(self):
        from sentinel.api.routes.performance import _get_conn

        mock_conn = MagicMock()
        mock_cfg = MagicMock()
        mock_cfg.host = "h"
        mock_cfg.port = 1
        mock_cfg.name = "db"
        mock_cfg.user = "u"
        mock_cfg.password = "p"
        mock_cfg.connect_timeout = 5

        mock_sentinel_cfg = MagicMock()
        mock_sentinel_cfg.database = mock_cfg

        with (
            patch("sentinel.api.routes.performance.load_config", return_value=mock_sentinel_cfg),
            patch(
                "sentinel.api.routes.performance.psycopg2.connect", return_value=mock_conn
            ) as mock_connect,
        ):
            _get_conn()

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["options"] == "-c search_path=axiom,public"


class TestPerfQueryHelper:
    def test_query_returns_rows_on_success(self):
        from sentinel.api.routes.performance import _query

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"cnt": 42}]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("sentinel.api.routes.performance._get_conn", return_value=mock_conn):
            result = _query("SELECT COUNT(*) AS cnt FROM predictions")

        assert result == [{"cnt": 42}]
        mock_conn.close.assert_called_once()

    def test_query_returns_empty_on_exception(self):
        from sentinel.api.routes.performance import _query

        with patch(
            "sentinel.api.routes.performance._get_conn",
            side_effect=Exception("connection refused"),
        ):
            result = _query("SELECT 1")

        assert result == []

    def test_query_passes_schema_to_get_conn(self):
        from sentinel.api.routes.performance import _query

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "sentinel.api.routes.performance._get_conn", return_value=mock_conn
        ) as mock_get_conn:
            _query("SELECT 1", schema="intelligence")

        mock_get_conn.assert_called_once_with("intelligence")

    def test_query_passes_params(self):
        from sentinel.api.routes.performance import _query

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("sentinel.api.routes.performance._get_conn", return_value=mock_conn):
            _query("SELECT * FROM t WHERE days = %s", (7,))

        mock_cursor.execute.assert_called_once_with("SELECT * FROM t WHERE days = %s", (7,))


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
