"""Data catalog engine — schema scanning, sensitive data classification, lineage."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Sensitive data patterns for auto-classification
SENSITIVE_PATTERNS: dict[str, re.Pattern] = {
    "api_key": re.compile(r"(api_key|apikey|api_secret|secret_key)", re.IGNORECASE),
    "token": re.compile(r"(token|bearer|auth_token|access_token|refresh_token)", re.IGNORECASE),
    "credential": re.compile(r"(password|passwd|credential|secret)", re.IGNORECASE),
    "sportsbook_key": re.compile(
        r"(book_key|sportsbook_auth|betting_token|proxy_auth)", re.IGNORECASE
    ),
    "email": re.compile(r"(email|e_mail)", re.IGNORECASE),
    "phone": re.compile(r"(phone|mobile|telephone)", re.IGNORECASE),
}

PII_PATTERNS: dict[str, re.Pattern] = {
    "financial": re.compile(r"(account_number|routing|credit_card|bank)", re.IGNORECASE),
    "credential": re.compile(r"(password|secret|token|api_key)", re.IGNORECASE),
    "identifier": re.compile(r"(ssn|driver_license|passport)", re.IGNORECASE),
}

# Masking rules by sensitive category
MASKING_RULES: dict[str, str] = {
    "api_key": "full_mask",
    "token": "full_mask",
    "credential": "full_mask",
    "sportsbook_key": "full_mask",
    "email": "partial_mask",
    "phone": "partial_mask",
}


class DataCatalogEngine:
    """Manages the data catalog, sensitive data classification, and lineage tracking."""

    def __init__(self, db):
        self.db = db

    def scan_schema(self, schema_name: str = "public") -> dict:
        """Scan database schema and auto-classify sensitive columns."""
        sql = """
            SELECT
                table_schema AS schema_name,
                table_name,
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
        """
        rows = self.db.execute_query(sql, (schema_name,))

        classified = 0
        for row in rows:
            column_name = row["column_name"]
            sensitive_category = self._classify_sensitive(column_name)
            is_pii = self._classify_pii(column_name)
            masking_rule = MASKING_RULES.get(sensitive_category) if sensitive_category else None

            self._upsert_catalog_entry(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                column_name=column_name,
                data_type=row["data_type"],
                is_phi=sensitive_category is not None,
                is_pii=is_pii,
                phi_category=sensitive_category,
                masking_rule=masking_rule,
            )
            if sensitive_category or is_pii:
                classified += 1

        logger.info(
            "Schema scan complete: %d columns scanned, %d sensitive classified",
            len(rows),
            classified,
        )
        return {
            "columns_scanned": len(rows),
            "phi_pii_classified": classified,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_catalog(self, table_name: str | None = None, phi_only: bool = False) -> list[dict]:
        """Retrieve catalog entries, optionally filtered."""
        conditions = ["1=1"]
        params: list = []

        if table_name:
            conditions.append("table_name = %s")
            params.append(table_name)
        if phi_only:
            conditions.append("is_phi = true")

        sql = (
            "SELECT id, schema_name, table_name, column_name, data_type, "
            "description, is_phi, is_pii, phi_category, masking_rule, "
            "retention_days, classification, last_scanned_at "
            f"FROM data_catalog WHERE {' AND '.join(conditions)} "
            "ORDER BY table_name, column_name"
        )
        return self.db.execute_query(sql, tuple(params))

    def get_lineage(self, pipeline_name: str | None = None, limit: int = 50) -> list[dict]:
        """Retrieve ETL lineage records."""
        if pipeline_name:
            sql = (
                "SELECT id, pipeline_name, execution_id, source_table, "
                "target_table, started_at, completed_at, status, rows_read, "
                "rows_written, rows_rejected, error_message "
                "FROM data_lineage WHERE pipeline_name = %s "
                "ORDER BY started_at DESC LIMIT %s"
            )
            return self.db.execute_query(sql, (pipeline_name, limit))

        sql = (
            "SELECT id, pipeline_name, execution_id, source_table, "
            "target_table, started_at, completed_at, status, rows_read, "
            "rows_written, rows_rejected, error_message "
            "FROM data_lineage ORDER BY started_at DESC LIMIT %s"
        )
        return self.db.execute_query(sql, (limit,))

    def record_lineage(
        self,
        pipeline_name: str,
        source_table: str,
        target_table: str,
        rows_read: int = 0,
        rows_written: int = 0,
        rows_rejected: int = 0,
        status: str = "success",
        error_message: str | None = None,
    ) -> int:
        """Record an ETL lineage entry from Python pipelines."""
        sql = """
            INSERT INTO data_lineage
                (pipeline_name, source_table, target_table, status,
                 completed_at, rows_read, rows_written, rows_rejected, error_message)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s)
            RETURNING id
        """
        result = self.db.execute_query(
            sql,
            (
                pipeline_name,
                source_table,
                target_table,
                status,
                rows_read,
                rows_written,
                rows_rejected,
                error_message,
            ),
        )
        return result[0]["id"] if result else 0

    def _classify_sensitive(self, column_name: str) -> str | None:
        """Check if a column name matches sensitive data patterns."""
        for category, pattern in SENSITIVE_PATTERNS.items():
            if pattern.search(column_name):
                return category
        return None

    def _classify_pii(self, column_name: str) -> bool:
        """Check if a column name matches PII patterns."""
        for pattern in PII_PATTERNS.values():
            if pattern.search(column_name):
                return True
        return False

    def mask_credentials_for_export(self) -> list[dict]:
        """Return API config data with credential fields masked for safe export."""
        rows = self.db.execute_query(
            "SELECT api_name, status, checked_at FROM api_health_log "
            "ORDER BY checked_at DESC LIMIT 50"
        )
        count = len(rows) if rows else 0
        self.log_access(
            user="system",
            action="MASKED_EXPORT",
            table="api_health_log",
            count=count,
            justification="Credential-masked export via governance API",
        )
        return rows or []

    def log_access(
        self,
        user: str,
        action: str,
        table: str,
        count: int,
        justification: str,
    ) -> None:
        """Record a sensitive data access event in the audit log."""
        try:
            self.db.execute_nonquery(
                "INSERT INTO phi_access_log "
                "(user_name, action, table_name, record_count, "
                "justification, access_time) "
                "VALUES (%s, %s, %s, %s, %s, NOW())",
                (user, action, table, count, justification),
            )
        except Exception as e:
            logger.warning("Failed to log access: %s", e)

    def _upsert_catalog_entry(self, **kwargs) -> None:
        """Insert or update a catalog entry."""
        sql = """
            INSERT INTO data_catalog
                (schema_name, table_name, column_name, data_type,
                 is_phi, is_pii, phi_category, masking_rule,
                 classification, last_scanned_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s THEN 'restricted' ELSE 'internal' END,
                    NOW())
            ON CONFLICT (schema_name, table_name, column_name) DO UPDATE SET
                data_type = EXCLUDED.data_type,
                is_phi = EXCLUDED.is_phi,
                is_pii = EXCLUDED.is_pii,
                phi_category = EXCLUDED.phi_category,
                masking_rule = EXCLUDED.masking_rule,
                last_scanned_at = NOW(),
                updated_at = NOW()
        """
        self.db.execute_nonquery(
            sql,
            (
                kwargs["schema_name"],
                kwargs["table_name"],
                kwargs["column_name"],
                kwargs["data_type"],
                kwargs["is_phi"],
                kwargs["is_pii"],
                kwargs["phi_category"],
                kwargs["masking_rule"],
                kwargs["is_phi"],  # for CASE expression
            ),
        )
