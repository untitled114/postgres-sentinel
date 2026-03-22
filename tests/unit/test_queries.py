"""Tests for SQL query loader — load_sql, load_pgstat, load_dmv."""

from __future__ import annotations

import pytest

from sentinel.db.queries import load_pgstat, load_sql


class TestLoadSql:
    def test_loads_existing_sql_file(self):
        """Load a known SQL file from the sql/ directory."""
        content = load_sql("pgstat/active_queries.sql")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_path_traversal_blocked(self):
        """Paths that escape the sql/ directory are rejected."""
        with pytest.raises(ValueError, match="Path traversal blocked"):
            load_sql("../../etc/passwd")

    def test_file_not_found(self):
        """Non-existent SQL files raise FileNotFoundError."""
        # Clear the lru_cache to avoid cached results
        load_sql.cache_clear()
        with pytest.raises(FileNotFoundError, match="SQL file not found"):
            load_sql("pgstat/nonexistent_query.sql")

    def test_result_is_cached(self):
        """Second call returns the same cached string object."""
        load_sql.cache_clear()
        first = load_sql("pgstat/active_queries.sql")
        second = load_sql("pgstat/active_queries.sql")
        assert first is second

    def test_loads_init_file(self):
        """Can load init SQL files."""
        content = load_sql("init/01_create_sentinel_schema.sql")
        assert "CREATE" in content.upper() or "create" in content.lower() or len(content) > 0


class TestLoadPgstat:
    def test_loads_by_name(self):
        """load_pgstat('active_queries') loads pgstat/active_queries.sql."""
        content = load_pgstat("active_queries")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_not_found(self):
        load_sql.cache_clear()
        with pytest.raises(FileNotFoundError):
            load_pgstat("totally_fake_query")


class TestLoadDmv:
    def test_load_dmv_is_alias(self):
        """load_dmv is an alias for load_pgstat."""
        from sentinel.db.queries import load_dmv

        assert load_dmv is load_pgstat
