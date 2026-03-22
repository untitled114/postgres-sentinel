"""Tests for ConnectionManager — psycopg2 PostgreSQL wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sentinel.config.models import DatabaseConfig
from sentinel.core.exceptions import DatabaseConnectionError, DatabaseQueryError
from sentinel.db.connection import ConnectionManager


@pytest.fixture
def db_config():
    return DatabaseConfig(
        host="localhost",
        port=5432,
        name="sentinel_test",
        user="sentinel",
        password="test_pass",
        connect_timeout=5,
        query_timeout=10,
    )


class TestConnectionManagerInit:
    def test_builds_dsn(self, db_config):
        cm = ConnectionManager(db_config)
        assert "host=localhost" in cm._dsn
        assert "port=5432" in cm._dsn
        assert "dbname=sentinel_test" in cm._dsn
        assert "user=sentinel" in cm._dsn

    def test_stores_config(self, db_config):
        cm = ConnectionManager(db_config)
        assert cm.config is db_config


class TestGetConnection:
    @patch("sentinel.db.connection.psycopg2.connect")
    def test_returns_connection(self, mock_connect, db_config):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        cm = ConnectionManager(db_config)
        conn = cm.get_connection()
        assert conn is mock_conn

    @patch("sentinel.db.connection.psycopg2.connect")
    def test_raises_on_operational_error(self, mock_connect, db_config):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError("cannot connect")

        cm = ConnectionManager(db_config)
        with pytest.raises(DatabaseConnectionError):
            cm.get_connection()

    @patch("sentinel.db.connection.psycopg2.connect")
    def test_raises_on_generic_error(self, mock_connect, db_config):
        import psycopg2

        mock_connect.side_effect = psycopg2.Error("unknown error")

        cm = ConnectionManager(db_config)
        with pytest.raises(DatabaseConnectionError):
            cm.get_connection()


class TestExecuteQuery:
    @patch("sentinel.db.connection.psycopg2.connect")
    def test_returns_list_of_dicts(self, mock_connect, db_config):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        cm = ConnectionManager(db_config)
        results = cm.execute_query("SELECT 1 AS ok")
        assert isinstance(results, list)

    @patch("sentinel.db.connection.psycopg2.connect")
    def test_passes_params(self, mock_connect, db_config):
        mock_cursor = MagicMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [{"count": 5}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        cm = ConnectionManager(db_config)
        cm.execute_query("SELECT COUNT(*) FROM predictions WHERE market = %s", ("POINTS",))
        mock_cursor.execute.assert_called()


class TestExecuteNonquery:
    @patch("sentinel.db.connection.psycopg2.connect")
    def test_returns_rowcount(self, mock_connect, db_config):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        cm = ConnectionManager(db_config)
        count = cm.execute_nonquery("DELETE FROM predictions WHERE id = %s", (1,))
        assert count == 3


class TestExecuteProc:
    @patch("sentinel.db.connection.psycopg2.connect")
    def test_calls_function(self, mock_connect, db_config):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [{"id": 1}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        cm = ConnectionManager(db_config)
        cm.execute_proc("fn_capture_health_snapshot")
        call_args = mock_cursor.execute.call_args[0][0]
        assert "fn_capture_health_snapshot" in call_args

    def test_rejects_invalid_proc_name(self, db_config):
        cm = ConnectionManager(db_config)
        with pytest.raises(ValueError, match="Invalid function name"):
            cm.execute_proc("DROP TABLE foo; --")


class TestTestConnection:
    @patch("sentinel.db.connection.psycopg2.connect")
    def test_returns_true_on_success(self, mock_connect, db_config):
        mock_cursor = MagicMock()
        mock_cursor.description = [("ok",)]
        mock_cursor.fetchall.return_value = [{"ok": 1}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        cm = ConnectionManager(db_config)
        assert cm.test_connection() is True

    @patch("sentinel.db.connection.psycopg2.connect")
    def test_returns_false_on_failure(self, mock_connect, db_config):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError("down")

        cm = ConnectionManager(db_config)
        assert cm.test_connection() is False
