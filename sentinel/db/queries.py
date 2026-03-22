"""SQL file loader — reads .sql files from disk and caches them."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent.parent / "sql"


@lru_cache(maxsize=64)
def load_sql(relative_path: str) -> str:
    """Load a SQL file relative to the sql/ directory.

    Example: load_sql("pgstat/active_queries.sql")
    """
    full_path = (SQL_DIR / relative_path).resolve()
    if not full_path.is_relative_to(SQL_DIR.resolve()):
        raise ValueError(f"Path traversal blocked: {relative_path}")
    if not full_path.exists():
        raise FileNotFoundError(f"SQL file not found: {full_path}")
    return full_path.read_text()


def load_pgstat(name: str) -> str:
    """Load a pg_stat query by name (without .sql extension)."""
    return load_sql(f"pgstat/{name}.sql")


# Keep backward-compatible alias during migration
load_dmv = load_pgstat
