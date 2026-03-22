"""Tests for configuration loading and validation."""

from sentinel.config.loader import _substitute_env_vars, _walk_and_substitute, load_yaml
from sentinel.config.models import (
    DatabaseConfig,
    JobConfig,
    SentinelConfig,
    ThresholdConfig,
    ValidationRuleConfig,
)


class TestEnvSubstitution:
    def test_simple_var(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert _substitute_env_vars("${TEST_VAR}") == "hello"

    def test_var_with_default(self):
        result = _substitute_env_vars("${NONEXISTENT_VAR:fallback}")
        assert result == "fallback"

    def test_no_substitution(self):
        assert _substitute_env_vars("plain text") == "plain text"

    def test_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        assert _substitute_env_vars("${A}-${B}") == "1-2"

    def test_walk_nested(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "myserver")
        data = {"db": {"host": "${DB_HOST}", "port": 1433}, "items": ["${DB_HOST}", "static"]}
        result = _walk_and_substitute(data)
        assert result["db"]["host"] == "myserver"
        assert result["items"][0] == "myserver"
        assert result["db"]["port"] == 1433


class TestLoadYaml:
    def test_load_valid_yaml(self, tmp_path):
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\nnested:\n  a: 1\n")
        result = load_yaml(yaml_file)
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1

    def test_load_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        result = load_yaml(yaml_file)
        assert result == {}


class TestPydanticModels:
    def test_database_config_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.host == "postgres"
        assert cfg.port == 5432
        assert cfg.name == "sentinel"

    def test_threshold_config_defaults(self):
        cfg = ThresholdConfig()
        assert cfg.cpu_percent_warning == 70.0
        assert cfg.cpu_percent_critical == 90.0

    def test_sentinel_config_minimal(self):
        cfg = SentinelConfig()
        assert cfg.database.host == "postgres"
        assert cfg.thresholds.cpu_percent_warning == 70.0
        assert cfg.jobs == []
        assert cfg.validation_rules == []

    def test_job_config(self):
        job = JobConfig(name="test_job", schedule_cron="*/5 * * * *", sql_inline="SELECT 1")
        assert job.name == "test_job"
        assert job.enabled is True
        assert job.timeout_seconds == 60

    def test_validation_rule_config(self):
        rule = ValidationRuleConfig(
            name="test", type="null_check", table="users", column="email", severity="critical"
        )
        assert rule.name == "test"
        assert rule.params == {}
