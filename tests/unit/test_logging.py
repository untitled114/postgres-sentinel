"""Tests for structured JSON logging — JsonFormatter and setup_logging."""

from __future__ import annotations

import json
import logging

from sentinel.core.logging import JsonFormatter, setup_logging


class TestJsonFormatter:
    def test_formats_basic_record_as_json(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="sentinel.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "sentinel.test"
        assert parsed["message"] == "Hello world"
        assert parsed["line"] == 42
        assert "timestamp" in parsed

    def test_includes_exception_info(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="sentinel.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Something failed",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "test error" in parsed["exception"]

    def test_no_exception_key_when_no_exc_info(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="t.py",
            lineno=1,
            msg="ok",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" not in parsed


class TestSetupLogging:
    def test_text_format_default(self):
        setup_logging(level="WARNING", json_output=False)
        root = logging.getLogger()
        assert root.level == logging.WARNING
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_json_format(self):
        setup_logging(level="DEBUG", json_output=True)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_reads_env_var_defaults(self, monkeypatch):
        monkeypatch.setenv("SENTINEL_LOG_LEVEL", "ERROR")
        monkeypatch.setenv("SENTINEL_LOG_FORMAT", "json")
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.ERROR
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_level_none_defaults_to_info(self, monkeypatch):
        monkeypatch.delenv("SENTINEL_LOG_LEVEL", raising=False)
        monkeypatch.delenv("SENTINEL_LOG_FORMAT", raising=False)
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_clears_existing_handlers(self):
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        assert len(root.handlers) >= 2
        setup_logging(level="INFO", json_output=False)
        assert len(root.handlers) == 1

    def test_invalid_level_falls_back_to_info(self):
        """An invalid level string defaults to INFO via getattr fallback."""
        setup_logging(level="NONEXISTENT", json_output=False)
        root = logging.getLogger()
        assert root.level == logging.INFO
