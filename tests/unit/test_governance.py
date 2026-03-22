"""Unit tests for data governance — sensitive data classification, catalog."""

from __future__ import annotations

import re

from sentinel.governance.catalog import (
    PII_PATTERNS,
    SENSITIVE_PATTERNS,
    DataCatalogEngine,
)


class TestSensitivePatterns:
    """Test sensitive data auto-classification patterns."""

    def test_detects_api_key(self):
        assert any(p.search("api_key") for p in SENSITIVE_PATTERNS.values())

    def test_detects_token(self):
        assert any(p.search("auth_token") for p in SENSITIVE_PATTERNS.values())

    def test_detects_password(self):
        assert any(p.search("password") for p in SENSITIVE_PATTERNS.values())

    def test_detects_email(self):
        assert any(p.search("email") for p in SENSITIVE_PATTERNS.values())

    def test_does_not_flag_player_name(self):
        engine = DataCatalogEngine(db=None)
        assert engine._classify_sensitive("player_name") is None

    def test_does_not_flag_game_date(self):
        engine = DataCatalogEngine(db=None)
        assert engine._classify_sensitive("game_date") is None

    def test_patterns_are_valid_regex(self):
        for name, pattern in SENSITIVE_PATTERNS.items():
            assert isinstance(pattern, re.Pattern), f"{name} is not a compiled regex"

    def test_pii_detects_credential(self):
        assert any(p.search("password") for p in PII_PATTERNS.values())

    def test_pii_patterns_are_valid_regex(self):
        for name, pattern in PII_PATTERNS.items():
            assert isinstance(pattern, re.Pattern), f"{name} is not a compiled regex"


class TestDataCatalogEngine:
    """Test catalog engine operations."""

    def test_get_catalog_returns_list(self, mock_db):
        engine = DataCatalogEngine(mock_db)
        entries = engine.get_catalog()
        assert isinstance(entries, list)

    def test_get_lineage_returns_list(self, mock_db):
        engine = DataCatalogEngine(mock_db)
        lineage = engine.get_lineage()
        assert isinstance(lineage, list)
