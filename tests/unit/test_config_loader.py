"""Tests for load_config() — full YAML merge pipeline."""

from __future__ import annotations

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
        assert any(r.name == "props_freshness" for r in config.validation_rules)
        # chaos_scenarios.yaml
        assert len(config.chaos_scenarios) > 0
        assert any(s.name == "Long Running Query" for s in config.chaos_scenarios)

    def test_returns_defaults_when_files_missing(self, tmp_path):
        """With empty config dir, load_config() returns defaults."""
        with patch("sentinel.config.loader.CONFIG_DIR", tmp_path):
            config = load_config()
        assert isinstance(config, SentinelConfig)
        assert config.database.host == "postgres"
        assert config.jobs == []
        assert config.validation_rules == []
        assert config.chaos_scenarios == []

    def test_partial_config_dir(self, tmp_path):
        """Only sentinel.yaml present — jobs/rules/chaos default to empty."""
        (tmp_path / "sentinel.yaml").write_text("thresholds:\n  cpu_percent_warning: 55.0\n")
        with patch("sentinel.config.loader.CONFIG_DIR", tmp_path):
            config = load_config()
        assert config.thresholds.cpu_percent_warning == 55.0
        assert config.jobs == []

    def test_env_var_substitution_in_config(self, monkeypatch, tmp_path):
        """Environment variables are substituted in YAML values."""
        monkeypatch.setenv("TEST_DB_HOST", "custom-host")
        (tmp_path / "sentinel.yaml").write_text("database:\n  host: '${TEST_DB_HOST}'\n")
        with patch("sentinel.config.loader.CONFIG_DIR", tmp_path):
            config = load_config()
        assert config.database.host == "custom-host"

    def test_sport_suite_thresholds_loaded(self):
        """Sport-suite thresholds are present in loaded config."""
        config = load_config()
        assert config.thresholds.win_rate_7d_warning == 55.0
        assert config.thresholds.win_rate_7d_critical == 50.0
        assert config.thresholds.line_snapshot_volume_warning == 10000
        assert config.thresholds.prediction_staleness_hours == 4.0
        assert config.thresholds.conviction_locked_pct_warning == 25.0
