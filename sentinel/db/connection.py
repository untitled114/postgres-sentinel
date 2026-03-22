"""psycopg2 connection manager for PostgreSQL."""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from sentinel.config.models import DatabaseConfig
from sentinel.core.exceptions import DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages psycopg2 connections to PostgreSQL."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._dsn = self._build_dsn()

    def _build_dsn(self) -> str:
        return (
            f"host={self.config.host} "
            f"port={self.config.port} "
            f"dbname={self.config.name} "
            f"user={self.config.user} "
            f"password={self.config.password} "
            f"connect_timeout={self.config.connect_timeout}"
        )

    def get_connection(self) -> psycopg2.extensions.connection:
        """Create and return a new database connection."""
        try:
            conn = psycopg2.connect(self._dsn)
            conn.autocommit = False
            if self.config.query_timeout:
                with conn.cursor() as cur:
                    cur.execute(
                        "SET statement_timeout = %s",
                        (self.config.query_timeout * 1000,),
                    )
            return conn
        except psycopg2.OperationalError as e:
            raise DatabaseConnectionError(f"Cannot connect to PostgreSQL: {e}") from e
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"Connection error: {e}") from e

    @contextmanager
    def cursor(self):
        """Context manager yielding a RealDictCursor that auto-commits and closes."""
        conn = self.get_connection()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            yield cur
            conn.commit()
        except psycopg2.OperationalError as e:
            conn.rollback()
            raise DatabaseQueryError(f"Query failed: {e}") from e
        except psycopg2.Error as e:
            conn.rollback()
            raise DatabaseQueryError(str(e)) from e
        finally:
            conn.close()

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a SELECT query and return rows as list of dicts."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            return [dict(row) for row in cur.fetchall()]

    def execute_nonquery(self, sql: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE and return rows affected."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def execute_proc(self, proc_name: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a PostgreSQL function and return results.

        Calls: SELECT * FROM proc_name(%s, %s, ...)
        """
        if not re.match(r"^[\w.]+$", proc_name):
            raise ValueError(f"Invalid function name: {proc_name}")
        placeholders = ", ".join(["%s"] * len(params))
        sql = f"SELECT * FROM {proc_name}({placeholders})"
        return self.execute_query(sql, params)

    def test_connection(self) -> bool:
        """Test if the database is reachable."""
        try:
            rows = self.execute_query("SELECT 1 AS ok")
            return len(rows) > 0 and rows[0].get("ok") == 1
        except (DatabaseConnectionError, DatabaseQueryError, psycopg2.Error) as e:
            logger.error("Connection test failed: %s", e)
            return False
