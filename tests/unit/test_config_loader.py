"""Tests for load_config() — full YAML merge pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sentinel.config.loader import load_config
from sentinel.config.models import SentinelConfig


class TestLoadConfig:
    def test_loads_all_yaml_files(self):
        """load_config() merges sentinel.yaml, jobs.yaml, rules.yaml, chaos.yaml."""
        config = load_config()
        assert isinstance(config, SentinelConfig)
        # sentinel.yaml thresholds
        assert config.thresholds.cpu_percent_warning == 70.0
        # jobs.yaml
        assert len(config.jobs) > 0
        assert any(j.name == "stale_session_cleanup" for j in config.jobs)
        # validation_rules.yaml
        assert len(config.validation_rules) > 0
        assert any(r.name == "customers_email_not_null" for r in config.validation_rules)
        # chaos_scenarios.yaml
        assert len(config.chaos_scenarios) > 0
        assert any(s.name == "Long Running Query" for s in config.chaos_scenarios)

    def test_returns_defaults_when_files_missing(self, tmp_path):
        """With empty config dir, load_config() returns defaults."""
        with patch("sentinel.config.loader.CONFIG_DIR", tmp_path):
            config = load_config()
        assert isinstance(config, SentinelConfig)
        assert config.database.host == "sqlserver"
        assert config.jobs == []
        assert config.validation_rules == []
        assert config.chaos_scenarios == []

    def test_partial_config_dir(self, tmp_path):
        """Only sentinel.yaml present — jobs/rules/chaos default to empty."""
        (tmp_path / "sentinel.yaml").write_text(
            "thresholds:\n  cpu_percent_warning: 55.0\n"
        )
        with patch("sentinel.config.loader.CONFIG_DIR", tmp_path):
            config = load_config()
        assert config.thresholds.cpu_percent_warning == 55.0
        assert config.jobs == []

    def test_env_var_substitution_in_config(self, monkeypatch, tmp_path):
        """Environment variables are substituted in YAML values."""
        monkeypatch.setenv("TEST_DB_HOST", "custom-host")
        (tmp_path / "sentinel.yaml").write_text(
            "database:\n  host: '${TEST_DB_HOST}'\n"
        )
        with patch("sentinel.config.loader.CONFIG_DIR", tmp_path):
            config = load_config()
        assert config.database.host == "custom-host"

    def test_kaggle_thresholds_loaded(self):
        """New Kaggle thresholds are present in loaded config."""
        config = load_config()
        assert config.thresholds.fraud_rate_warning == 1.0
        assert config.thresholds.fraud_rate_critical == 5.0
        assert config.thresholds.admission_emergency_rate_warning == 40.0
        assert config.thresholds.covid_mortality_rate_warning == 15.0
        assert config.thresholds.insurance_high_risk_pct_warning == 30.0
