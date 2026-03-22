"""Validation rule implementations."""

from __future__ import annotations

import logging
import re
from typing import Any

from sentinel.db.connection import ConnectionManager

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[\w]+$")


def _safe_ident(name: str) -> str:
    """Validate and quote a PostgreSQL identifier. Raises ValueError if invalid."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


class ValidationRule:
    """Base class for data validation rules."""

    def __init__(
        self,
        name: str,
        rule_type: str,
        table: str,
        column: str,
        severity: str,
        params: dict,
        description: str,
    ):
        self.name = name
        self.rule_type = rule_type
        self.table = table
        self.column = column
        self.severity = severity
        self.params = params
        self.description = description

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        """Execute the rule and return result dict."""
        raise NotImplementedError


class NullCheckRule(ValidationRule):
    """Check for unexpected NULL values in a column."""

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        tbl = _safe_ident(self.table)
        col = _safe_ident(self.column)
        rows = db.execute_query(f"SELECT COUNT(*) AS cnt FROM {tbl} WHERE {col} IS NULL")
        count = rows[0]["cnt"] if rows else 0
        samples = []
        if count > 0:
            sample_rows = db.execute_query(
                f"SELECT * FROM {tbl} WHERE {col} IS NULL LIMIT 5"
            )
            samples = [str(r) for r in sample_rows]
        return {"passed": count == 0, "violation_count": count, "sample_values": samples}


class RangeCheckRule(ValidationRule):
    """Check that column values fall within expected range."""

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        tbl = _safe_ident(self.table)
        col = _safe_ident(self.column)
        min_val = self.params.get("min")
        max_val = self.params.get("max")

        # Build parameterized range conditions
        conditions = []
        params: list = []
        if min_val is not None:
            conditions.append(f"{col} < %s")
            params.append(float(min_val))
        if max_val is not None:
            conditions.append(f"{col} > %s")
            params.append(float(max_val))
        if not conditions:
            return {"passed": True, "violation_count": 0, "sample_values": []}

        where = " OR ".join(conditions)
        rows = db.execute_query(
            f"SELECT COUNT(*) AS cnt FROM {tbl} WHERE {where}", tuple(params)
        )
        count = rows[0]["cnt"] if rows else 0
        samples = []
        if count > 0:
            sample_rows = db.execute_query(
                f"SELECT {col} FROM {tbl} WHERE {where} LIMIT 5", tuple(params)
            )
            samples = [str(r.get(self.column)) for r in sample_rows]
        return {"passed": count == 0, "violation_count": count, "sample_values": samples}


class ReferentialRule(ValidationRule):
    """Check referential integrity between tables."""

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        tbl = _safe_ident(self.table)
        col = _safe_ident(self.column)
        ref_tbl = _safe_ident(self.params.get("ref_table", ""))
        ref_col = _safe_ident(self.params.get("ref_column", "id"))
        rows = db.execute_query(
            f"SELECT COUNT(*) AS cnt FROM {tbl} t "
            f"LEFT JOIN {ref_tbl} r ON t.{col} = r.{ref_col} "
            f"WHERE r.{ref_col} IS NULL AND t.{col} IS NOT NULL"
        )
        count = rows[0]["cnt"] if rows else 0
        samples = []
        if count > 0:
            sample_rows = db.execute_query(
                f"SELECT t.{col} FROM {tbl} t "
                f"LEFT JOIN {ref_tbl} r ON t.{col} = r.{ref_col} "
                f"WHERE r.{ref_col} IS NULL AND t.{col} IS NOT NULL "
                f"LIMIT 5"
            )
            samples = [str(r.get(self.column)) for r in sample_rows]
        return {"passed": count == 0, "violation_count": count, "sample_values": samples}


class DuplicateRule(ValidationRule):
    """Check for duplicate values in a column or column group."""

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        columns = self.params.get("columns", [self.column])
        col_list = ", ".join(_safe_ident(c) for c in columns)
        tbl = _safe_ident(self.table)
        rows = db.execute_query(
            f"SELECT {col_list}, COUNT(*) AS cnt FROM {tbl} "
            f"GROUP BY {col_list} HAVING COUNT(*) > 1"
        )
        count = len(rows)
        samples = [str(r) for r in rows[:5]]
        return {"passed": count == 0, "violation_count": count, "sample_values": samples}


class FreshnessRule(ValidationRule):
    """Check that recent data exists (table isn't stale)."""

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        tbl = _safe_ident(self.table)
        col = _safe_ident(self.column)
        max_age_hours = int(self.params.get("max_age_hours", 24))
        rows = db.execute_query(
            f"SELECT COUNT(*) AS cnt FROM {tbl} "
            f"WHERE {col} >= NOW() - INTERVAL '%s hours'",
            (max_age_hours,),
        )
        count = rows[0]["cnt"] if rows else 0
        passed = count > 0
        return {
            "passed": passed,
            "violation_count": 0 if passed else 1,
            "sample_values": [f"Recent rows: {count}"],
        }


class CustomSqlRule(ValidationRule):
    """Run arbitrary SQL — expects a single 'violation_count' column."""

    def execute(self, db: ConnectionManager) -> dict[str, Any]:
        sql = self.params.get("sql", "")
        if not sql:
            return {"passed": True, "violation_count": 0, "sample_values": []}
        rows = db.execute_query(sql)
        count = rows[0].get("violation_count", 0) if rows else 0
        return {
            "passed": count == 0,
            "violation_count": count,
            "sample_values": [str(r) for r in rows[:5]],
        }


RULE_TYPES: dict[str, type[ValidationRule]] = {
    "null_check": NullCheckRule,
    "range_check": RangeCheckRule,
    "referential": ReferentialRule,
    "duplicate": DuplicateRule,
    "freshness": FreshnessRule,
    "custom_sql": CustomSqlRule,
}


def create_rule(config: dict) -> ValidationRule:
    """Factory: create a rule instance from config dict."""
    rule_type = config.get("type", "")
    cls = RULE_TYPES.get(rule_type)
    if not cls:
        raise ValueError(f"Unknown rule type: {rule_type}")
    return cls(
        name=config.get("name", "unnamed"),
        rule_type=rule_type,
        table=config.get("table", ""),
        column=config.get("column", ""),
        severity=config.get("severity", "warning"),
        params=config.get("params", {}),
        description=config.get("description", ""),
    )
