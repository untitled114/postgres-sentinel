"""Validation engine — runs all rules, saves results, generates scorecard."""

from __future__ import annotations

import json
import logging
from typing import Any

from sentinel.config.models import ValidationRuleConfig
from sentinel.core.exceptions import DatabaseQueryError, ValidationRuleError
from sentinel.db.connection import ConnectionManager
from sentinel.validation.rules import create_rule

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Runs configured validation rules and persists results."""

    def __init__(self, db: ConnectionManager, rules: list[ValidationRuleConfig]):
        self.db = db
        self.rules = rules

    def run_all(self) -> list[dict[str, Any]]:
        """Execute all validation rules and save results."""
        results = []
        for rule_cfg in self.rules:
            result = self._run_single(rule_cfg)
            results.append(result)
        return results

    def _run_single(self, rule_cfg: ValidationRuleConfig) -> dict[str, Any]:
        """Execute a single validation rule."""
        try:
            rule = create_rule(rule_cfg.model_dump())
            outcome = rule.execute(self.db)
        except (DatabaseQueryError, ValidationRuleError) as e:
            logger.error("Validation rule '%s' failed: %s", rule_cfg.name, e)
            outcome = {"passed": False, "violation_count": -1, "sample_values": [str(e)]}

        result = {
            "rule_name": rule_cfg.name,
            "rule_type": rule_cfg.type,
            "table_name": rule_cfg.table,
            "column_name": rule_cfg.column,
            "severity": rule_cfg.severity,
            "description": rule_cfg.description,
            **outcome,
        }

        # Persist to DB
        try:
            self.db.execute_nonquery(
                "INSERT INTO validation_results (rule_name, rule_type, table_name, column_name, "
                "passed, severity, violation_count, sample_values, description) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    result["rule_name"],
                    result["rule_type"],
                    result["table_name"],
                    result["column_name"],
                    1 if result["passed"] else 0,
                    result["severity"],
                    result["violation_count"],
                    json.dumps(result.get("sample_values", [])),
                    result["description"],
                ),
            )
        except DatabaseQueryError as e:
            logger.warning("Failed to persist validation result for '%s': %s", rule_cfg.name, e)

        return result

    def get_scorecard(self) -> dict[str, Any]:
        """Generate a scorecard from the latest run of each rule."""
        rows = self.db.execute_query(
            "WITH latest_run AS ("
            "  SELECT *, ROW_NUMBER() OVER (PARTITION BY rule_name ORDER BY executed_at DESC) AS rn"
            "  FROM validation_results"
            ") SELECT * FROM latest_run WHERE rn = 1 ORDER BY passed, severity DESC"
        )

        total = len(rows)
        passed = sum(1 for r in rows if r.get("passed"))
        failed = total - passed
        critical_failures = sum(
            1 for r in rows if not r.get("passed") and r.get("severity") == "critical"
        )

        return {
            "total_rules": total,
            "passed": passed,
            "failed": failed,
            "critical_failures": critical_failures,
            "score_percent": round((passed / total) * 100, 1) if total > 0 else 0,
            "rules": rows,
        }

    def get_recent_results(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent validation results."""
        return self.db.execute_query(
            "SELECT * FROM validation_results ORDER BY executed_at DESC LIMIT %s", (limit,)
        )
