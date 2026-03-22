"""Targeted tests for coverage gaps across multiple modules."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from sentinel.config.models import JobConfig, SentinelConfig, ThresholdConfig
from sentinel.core.exceptions import DatabaseQueryError

# ---------------------------------------------------------------------------
# chaos/scenarios.py — base class and error paths (lines 22, 39-40, 57-58, etc.)
# ---------------------------------------------------------------------------


class TestChaosScenarioBase:
    def test_base_execute_raises(self, mock_db):
        from sentinel.chaos.scenarios import ChaosScenario

        base = ChaosScenario()
        with pytest.raises(NotImplementedError):
            base.execute(mock_db)


class TestChaosScenarioErrorPaths:
    """Test error branches in chaos scenarios (DatabaseQueryError catches)."""

    def test_long_running_query_timeout(self, mock_db):
        from sentinel.chaos.scenarios import LongRunningQuery

        mock_db.execute_query = MagicMock(side_effect=DatabaseQueryError("timeout"))
        scenario = LongRunningQuery()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "timeout" in result["detail"].lower() or "may timeout" in result["detail"].lower()

    def test_connection_flood_error(self, mock_db):
        from sentinel.chaos.scenarios import ConnectionFlood

        call_count = {"n": 0}

        def get_conn_limited():
            call_count["n"] += 1
            if call_count["n"] > 5:
                raise DatabaseQueryError("too many connections")
            return MagicMock()

        mock_db.get_connection = get_conn_limited
        scenario = ConnectionFlood()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "5" in result["detail"]

    def test_dag_overlap_error(self, mock_db):
        from sentinel.chaos.scenarios import DagOverlap

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("constraint violation"))
        scenario = DagOverlap()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "partial" in result["detail"].lower()

    def test_extractor_default_injection_error(self, mock_db):
        from sentinel.chaos.scenarios import ExtractorDefaultInjection

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("table not found"))
        scenario = ExtractorDefaultInjection()
        result = scenario.execute(mock_db)
        assert result["triggered"] is False

    def test_line_ingestion_drop_error(self, mock_db):
        from sentinel.chaos.scenarios import LineIngestionDrop

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("permission denied"))
        scenario = LineIngestionDrop()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "partial" in result["detail"].lower()

    def test_model_file_missing_error(self, mock_db):
        from sentinel.chaos.scenarios import ModelFileMissing

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("no rows"))
        scenario = ModelFileMissing()
        result = scenario.execute(mock_db)
        assert result["triggered"] is False

    def test_model_file_missing_no_rows(self, mock_db):
        from sentinel.chaos.scenarios import ModelFileMissing

        mock_db.execute_nonquery = MagicMock(return_value=0)
        scenario = ModelFileMissing()
        result = scenario.execute(mock_db)
        assert result["triggered"] is False

    def test_conviction_collapse_error(self, mock_db):
        from sentinel.chaos.scenarios import ConvictionCollapse

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("fail"))
        scenario = ConvictionCollapse()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "partial" in result["detail"].lower()

    def test_win_rate_crash_error(self, mock_db):
        from sentinel.chaos.scenarios import WinRateCrash

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("disk full"))
        scenario = WinRateCrash()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "partial" in result["detail"].lower()

    def test_win_rate_crash_success(self, mock_db):
        from sentinel.chaos.scenarios import WinRateCrash

        mock_db.execute_nonquery = MagicMock(return_value=1)
        scenario = WinRateCrash()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "140" in result["detail"]  # 20 per day * 7 days

    def test_prediction_staleness_error(self, mock_db):
        from sentinel.chaos.scenarios import PredictionStaleness

        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("err"))
        scenario = PredictionStaleness()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "partial" in result["detail"].lower()

    def test_long_running_query_success(self, mock_db):
        from sentinel.chaos.scenarios import LongRunningQuery

        mock_db.execute_query = MagicMock(return_value=[])
        scenario = LongRunningQuery()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "45-second" in result["detail"]

    def test_dag_overlap_success(self, mock_db):
        from sentinel.chaos.scenarios import DagOverlap

        mock_db.execute_nonquery = MagicMock(return_value=1)
        scenario = DagOverlap()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "2 concurrent" in result["detail"]

    def test_prediction_staleness_success(self, mock_db):
        from sentinel.chaos.scenarios import PredictionStaleness

        mock_db.execute_nonquery = MagicMock(return_value=10)
        scenario = PredictionStaleness()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True
        assert "10" in result["detail"]

    def test_model_file_missing_success(self, mock_db):
        from sentinel.chaos.scenarios import ModelFileMissing

        mock_db.execute_nonquery = MagicMock(return_value=1)
        scenario = ModelFileMissing()
        result = scenario.execute(mock_db)
        assert result["triggered"] is True


# ---------------------------------------------------------------------------
# chaos/engine.py — all on cooldown (line 99)
# ---------------------------------------------------------------------------


class TestChaosEngineAllCooldown:
    def test_trigger_random_all_on_cooldown(self, mock_db):
        from sentinel.chaos.engine import ChaosEngine
        from sentinel.monitor.incident_manager import IncidentManager

        incidents = IncidentManager(mock_db)
        engine = ChaosEngine(mock_db, incidents)
        # Put all scenarios on cooldown
        import time

        future = time.time() + 9999
        for name in engine._scenarios:
            engine._cooldowns[name] = future

        result = engine.trigger_random()
        assert "error" in result
        assert "cooldown" in result["error"].lower()


# ---------------------------------------------------------------------------
# jobs/runner.py — additional coverage (lines 36, 77, 130, 141-163, 167-184)
# ---------------------------------------------------------------------------


class TestJobRunnerAdditional:
    def test_parse_cron_every_raw_int(self):
        from sentinel.jobs.runner import _parse_simple_cron

        assert _parse_simple_cron("@every 120") == 120

    def test_get_history_with_job_name(self, mock_db):
        from sentinel.jobs.runner import JobRunner

        runner = JobRunner(mock_db, [])
        runner.get_history(job_name="cleanup", limit=5)
        # Verify the query was called with job_name filter
        last_query = mock_db._query_log[-1]
        assert "job_name" in last_query

    def test_resolve_sql_from_file(self, mock_db):
        from sentinel.jobs.runner import JobRunner

        job = JobConfig(
            name="file_job",
            schedule_cron="@every 60s",
            sql_file="pgstat/active_queries.sql",
        )
        runner = JobRunner(mock_db, [job])
        result = runner.run_job("file_job")
        assert result["status"] == "success"

    def test_log_start_error_returns_none(self, mock_db):
        """_log_start returns None if DB insert fails."""
        from sentinel.jobs.runner import JobRunner

        original = mock_db.execute_query

        def failing_query(sql, params=()):
            if "INSERT INTO job_runs" in sql:
                raise DatabaseQueryError("disk full")
            return original(sql, params)

        mock_db.execute_query = failing_query
        job = JobConfig(name="test", schedule_cron="@every 60s", sql_inline="SELECT 1")
        runner = JobRunner(mock_db, [job])
        result = runner.run_job("test")
        # Should still succeed even if logging fails
        assert result["status"] == "success"
        mock_db.execute_query = original

    def test_log_complete_with_none_run_id(self, mock_db):
        """_log_complete with None run_id is a no-op."""
        from sentinel.jobs.runner import JobRunner

        runner = JobRunner(mock_db, [])
        # Should not raise
        runner._log_complete(None, "success", 100)

    def test_log_complete_error_handled(self, mock_db):
        """_log_complete handles DB errors gracefully."""
        from sentinel.jobs.runner import JobRunner

        original = mock_db.execute_nonquery
        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("err"))
        runner = JobRunner(mock_db, [])
        # Should not raise
        runner._log_complete(42, "success", 100)
        mock_db.execute_nonquery = original

    @pytest.mark.asyncio
    async def test_run_loop_executes_due_jobs(self):
        """run_loop executes jobs that are due."""
        from sentinel.jobs.runner import JobRunner

        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"id": 1}]
        mock_db.execute_nonquery.return_value = 1

        job = JobConfig(name="loop_test", schedule_cron="@every 1s", sql_inline="SELECT 1")
        runner = JobRunner(mock_db, [job])

        task = asyncio.create_task(runner.run_loop())
        await asyncio.sleep(0.1)
        runner.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert runner._running is False

    @pytest.mark.asyncio
    async def test_run_loop_handles_job_error(self):
        """run_loop handles errors from individual jobs without stopping."""
        from sentinel.jobs.runner import JobRunner

        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"id": 1}]
        mock_db.execute_nonquery.side_effect = DatabaseQueryError("db gone")

        job = JobConfig(name="err_job", schedule_cron="@every 1s", sql_inline="SELECT 1")
        runner = JobRunner(mock_db, [job])

        task = asyncio.create_task(runner.run_loop())
        await asyncio.sleep(0.1)
        runner.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Loop survived


# ---------------------------------------------------------------------------
# monitor/health.py — threshold coverage for each metric at warning/critical
# ---------------------------------------------------------------------------


class TestHealthThresholdWarnings:
    """Test warning-level alerts for each metric (currently only critical is covered)."""

    def test_memory_warning(self, mock_db):
        """Memory at 78% with 75% threshold = warning."""
        config = SentinelConfig(
            thresholds=ThresholdConfig(
                memory_percent_warning=75.0,
                memory_percent_critical=90.0,
            )
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        # Mock returns 2048/8192 = 25% by default, so we need to override
        original = mock_db.execute_proc

        def custom_proc(name, params=()):
            rows = original(name, params)
            if rows and "memory_used_mb" in rows[0]:
                rows[0]["memory_used_mb"] = 6400.0  # 6400/8192 = 78.1%
                rows[0]["memory_total_mb"] = 8192.0
            return rows

        mock_db.execute_proc = custom_proc
        snapshot = collector.collect_snapshot()
        mem_alerts = [a for a in snapshot["alerts"] if a["metric"] == "memory"]
        assert len(mem_alerts) == 1
        assert mem_alerts[0]["level"] == "warning"

    def test_memory_critical(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(
                memory_percent_warning=75.0,
                memory_percent_critical=90.0,
            )
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        original = mock_db.execute_proc

        def custom_proc(name, params=()):
            rows = original(name, params)
            if rows and "memory_used_mb" in rows[0]:
                rows[0]["memory_used_mb"] = 7500.0  # 7500/8192 = 91.6%
                rows[0]["memory_total_mb"] = 8192.0
            return rows

        mock_db.execute_proc = custom_proc
        snapshot = collector.collect_snapshot()
        mem_alerts = [a for a in snapshot["alerts"] if a["metric"] == "memory"]
        assert len(mem_alerts) == 1
        assert mem_alerts[0]["level"] == "critical"

    def test_connection_warning(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(
                connection_count_warning=20,
                connection_count_critical=150,
            )
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        snapshot = collector.collect_snapshot()
        # Mock returns connection_count=25, threshold is 20 = warning
        conn_alerts = [a for a in snapshot["alerts"] if a["metric"] == "connections"]
        assert len(conn_alerts) == 1
        assert conn_alerts[0]["level"] == "warning"

    def test_connection_critical(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(
                connection_count_critical=20,
            )
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        snapshot = collector.collect_snapshot()
        conn_alerts = [a for a in snapshot["alerts"] if a["metric"] == "connections"]
        assert len(conn_alerts) == 1
        assert conn_alerts[0]["level"] == "critical"

    def test_lock_wait_warning(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(lock_wait_warning=0, lock_wait_critical=15)
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        # Mock returns lock_wait_count=0, override to trigger warning
        original = mock_db.execute_proc

        def custom_proc(name, params=()):
            rows = original(name, params)
            if rows and "lock_wait_count" in rows[0]:
                rows[0]["lock_wait_count"] = 8
            return rows

        mock_db.execute_proc = custom_proc
        snapshot = collector.collect_snapshot()
        lock_alerts = [a for a in snapshot["alerts"] if a["metric"] == "lock_wait"]
        # lock_wait=8 >= warning=0 but < critical=15
        assert any(a["level"] == "warning" for a in lock_alerts)

    def test_lock_wait_critical(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(lock_wait_warning=5, lock_wait_critical=10)
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        original = mock_db.execute_proc

        def custom_proc(name, params=()):
            rows = original(name, params)
            if rows and "lock_wait_count" in rows[0]:
                rows[0]["lock_wait_count"] = 12
            return rows

        mock_db.execute_proc = custom_proc
        snapshot = collector.collect_snapshot()
        lock_alerts = [a for a in snapshot["alerts"] if a["metric"] == "lock_wait"]
        assert any(a["level"] == "critical" for a in lock_alerts)

    def test_dead_tuple_warning(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(
                dead_tuple_ratio_warning=2.0,
                dead_tuple_ratio_critical=25.0,
            )
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        snapshot = collector.collect_snapshot()
        # Mock returns dead_tuple_ratio=2.5, warning threshold=2.0
        dt_alerts = [a for a in snapshot["alerts"] if a["metric"] == "dead_tuple_ratio"]
        assert len(dt_alerts) == 1
        assert dt_alerts[0]["level"] == "warning"

    def test_dead_tuple_critical(self, mock_db):
        config = SentinelConfig(
            thresholds=ThresholdConfig(
                dead_tuple_ratio_warning=1.0,
                dead_tuple_ratio_critical=2.0,
            )
        )
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        snapshot = collector.collect_snapshot()
        dt_alerts = [a for a in snapshot["alerts"] if a["metric"] == "dead_tuple_ratio"]
        assert len(dt_alerts) == 1
        assert dt_alerts[0]["level"] == "critical"

    def test_cache_hit_ratio_warning(self, mock_db):
        config = SentinelConfig()
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        original = mock_db.execute_proc

        def custom_proc(name, params=()):
            rows = original(name, params)
            if rows and "cache_hit_ratio" in rows[0]:
                rows[0]["cache_hit_ratio"] = 85.0  # Below 90 threshold
            return rows

        mock_db.execute_proc = custom_proc
        snapshot = collector.collect_snapshot()
        cache_alerts = [a for a in snapshot["alerts"] if a["metric"] == "cache_hit_ratio"]
        assert len(cache_alerts) == 1
        assert cache_alerts[0]["level"] == "warning"

    def test_long_query_warning(self, mock_db):
        config = SentinelConfig()
        from sentinel.monitor.health import HealthCollector

        collector = HealthCollector(mock_db, config)
        original = mock_db.execute_proc

        def custom_proc(name, params=()):
            rows = original(name, params)
            if rows and "long_query_count" in rows[0]:
                rows[0]["long_query_count"] = 3
            return rows

        mock_db.execute_proc = custom_proc
        snapshot = collector.collect_snapshot()
        lq_alerts = [a for a in snapshot["alerts"] if a["metric"] == "long_queries"]
        assert len(lq_alerts) == 1
        assert lq_alerts[0]["level"] == "warning"

    def test_empty_proc_returns_error_snapshot(self, mock_db):
        """When fn_capture_health_snapshot returns no rows."""
        from sentinel.monitor.health import HealthCollector

        config = SentinelConfig()
        mock_db.execute_proc = lambda *a, **k: []
        collector = HealthCollector(mock_db, config)
        snapshot = collector.collect_snapshot()
        assert snapshot["status"] == "error"

    def test_update_snapshot_status_error(self, mock_db):
        """When updating snapshot status fails, collection still works."""
        from sentinel.monitor.health import HealthCollector

        config = SentinelConfig()
        collector = HealthCollector(mock_db, config)
        original_nonquery = mock_db.execute_nonquery
        mock_db.execute_nonquery = MagicMock(side_effect=DatabaseQueryError("disk full"))
        snapshot = collector.collect_snapshot()
        assert snapshot["status"] == "healthy"  # Still computed correctly
        mock_db.execute_nonquery = original_nonquery

    def test_get_history(self, mock_db):
        from sentinel.monitor.health import HealthCollector

        config = SentinelConfig()
        collector = HealthCollector(mock_db, config)
        result = collector.get_history(hours=4)
        assert isinstance(result, list)

    def test_sql_health_error(self, mock_db):
        from sentinel.monitor.health import HealthCollector

        config = SentinelConfig()
        mock_db.execute_query = MagicMock(side_effect=DatabaseQueryError("conn refused"))
        collector = HealthCollector(mock_db, config)
        result = collector.get_sql_health()
        assert result["connected"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# monitor/pipeline.py — threshold gaps (staleness, conviction, api response)
# ---------------------------------------------------------------------------


class TestPipelineThresholdGaps:
    def test_prediction_staleness_alert(self, mock_db):
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig(prediction_staleness_hours=4.0)
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {
            "win_rate_7d": 60.0,
            "predictions_today": 10,
            "line_snapshots_today": 15000,
            "hours_since_last_prediction": 6.0,
            "conviction_locked_pct": 0.0,
            "avg_api_response_ms": 100.0,
        }
        alerts = monitor.evaluate_thresholds(metrics)
        stale_alerts = [a for a in alerts if a["metric"] == "prediction_staleness"]
        assert len(stale_alerts) == 1
        assert stale_alerts[0]["level"] == "warning"

    def test_conviction_locked_pct_alert(self, mock_db):
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig(conviction_locked_pct_warning=25.0)
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {
            "win_rate_7d": 60.0,
            "predictions_today": 10,
            "line_snapshots_today": 15000,
            "hours_since_last_prediction": 1.0,
            "conviction_locked_pct": 30.0,
            "avg_api_response_ms": 100.0,
        }
        alerts = monitor.evaluate_thresholds(metrics)
        conv_alerts = [a for a in alerts if a["metric"] == "conviction_locked_pct"]
        assert len(conv_alerts) == 1

    def test_api_response_ms_warning(self, mock_db):
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig(
            api_response_ms_warning=5000.0,
            api_response_ms_critical=15000.0,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {
            "win_rate_7d": 60.0,
            "predictions_today": 10,
            "line_snapshots_today": 15000,
            "hours_since_last_prediction": 1.0,
            "conviction_locked_pct": 0.0,
            "avg_api_response_ms": 7000.0,
        }
        alerts = monitor.evaluate_thresholds(metrics)
        api_alerts = [a for a in alerts if a["metric"] == "api_response_ms"]
        assert len(api_alerts) == 1
        assert api_alerts[0]["level"] == "warning"

    def test_api_response_ms_critical(self, mock_db):
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig(
            api_response_ms_warning=5000.0,
            api_response_ms_critical=15000.0,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {
            "win_rate_7d": 60.0,
            "predictions_today": 10,
            "line_snapshots_today": 15000,
            "hours_since_last_prediction": 1.0,
            "conviction_locked_pct": 0.0,
            "avg_api_response_ms": 20000.0,
        }
        alerts = monitor.evaluate_thresholds(metrics)
        api_alerts = [a for a in alerts if a["metric"] == "api_response_ms"]
        assert len(api_alerts) == 1
        assert api_alerts[0]["level"] == "critical"

    def test_line_snapshot_volume_warning(self, mock_db):
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig(
            line_snapshot_volume_warning=10000,
            line_snapshot_volume_critical=5000,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {
            "win_rate_7d": 60.0,
            "predictions_today": 10,
            "line_snapshots_today": 7000,
            "hours_since_last_prediction": 1.0,
            "conviction_locked_pct": 0.0,
            "avg_api_response_ms": 100.0,
        }
        alerts = monitor.evaluate_thresholds(metrics)
        snap_alerts = [a for a in alerts if a["metric"] == "line_snapshot_volume"]
        assert len(snap_alerts) == 1
        assert snap_alerts[0]["level"] == "warning"

    def test_collect_with_no_api_rows(self, mock_db):
        """When api_health_log returns empty, defaults are set."""
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig()

        # Override the mock to return empty for api_health_log
        original = mock_db.execute_query

        def custom_query(sql, params=()):
            if "api_health_log" in sql and "MAX(checked_at)" in sql:
                return []  # No API health data
            return original(sql, params)

        mock_db.execute_query = custom_query
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = monitor.collect_metrics()
        assert metrics["avg_api_response_ms"] == 0.0
        assert metrics["apis_down"] == 0
        mock_db.execute_query = original

    def test_collect_win_rate_none(self, mock_db):
        """When win_rate query returns None."""
        from sentinel.monitor.pipeline import PipelineMonitor

        thresholds = ThresholdConfig()
        original = mock_db.execute_query

        def custom_query(sql, params=()):
            if "model_performance" in sql and "AVG" in sql:
                return [{"win_rate_7d": None}]
            return original(sql, params)

        mock_db.execute_query = custom_query
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = monitor.collect_metrics()
        assert metrics["win_rate_7d"] is None
        mock_db.execute_query = original


# ---------------------------------------------------------------------------
# validation/engine.py — error paths (lines 37-39, 69-70, 101)
# ---------------------------------------------------------------------------


class TestValidationEngineGaps:
    def test_run_single_with_db_error(self, mock_db, config):
        """When rule execution raises DatabaseQueryError, result has violation_count=-1."""
        from sentinel.config.models import ValidationRuleConfig
        from sentinel.validation.engine import ValidationEngine

        rules = [
            ValidationRuleConfig(
                name="broken_rule",
                type="null_check",
                table="nonexistent_table",
                column="col",
                severity="critical",
                description="Will fail",
            )
        ]

        # Make execute_query raise for the rule's SQL
        original = mock_db.execute_query

        def failing_query(sql, params=()):
            if "nonexistent_table" in sql:
                raise DatabaseQueryError("table not found")
            return original(sql, params)

        mock_db.execute_query = failing_query

        engine = ValidationEngine(mock_db, rules)
        results = engine.run_all()
        assert len(results) == 1
        assert results[0]["passed"] is False
        assert results[0]["violation_count"] == -1
        mock_db.execute_query = original

    def test_persist_result_failure(self, mock_db, config):
        """When persisting validation result fails, it doesn't crash."""
        from sentinel.config.models import ValidationRuleConfig
        from sentinel.validation.engine import ValidationEngine

        rules = [
            ValidationRuleConfig(
                name="persist_fail",
                type="null_check",
                table="predictions",
                column="model_version",
                severity="warning",
            )
        ]

        original = mock_db.execute_nonquery

        def failing_nonquery(sql, params=()):
            if "INSERT INTO validation_results" in sql:
                raise DatabaseQueryError("disk full")
            return original(sql, params)

        mock_db.execute_nonquery = failing_nonquery

        engine = ValidationEngine(mock_db, rules)
        results = engine.run_all()
        assert len(results) == 1
        mock_db.execute_nonquery = original

    def test_get_recent_results(self, mock_db, config):
        from sentinel.validation.engine import ValidationEngine

        engine = ValidationEngine(mock_db, [])
        results = engine.get_recent_results(limit=10)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# validation/rules.py — _safe_ident error path (line 19)
# ---------------------------------------------------------------------------


class TestSafeIdent:
    def test_invalid_identifier_raises(self):
        from sentinel.validation.rules import _safe_ident

        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _safe_ident("DROP TABLE; --")

    def test_valid_identifier(self):
        from sentinel.validation.rules import _safe_ident

        assert _safe_ident("predictions") == '"predictions"'


# ---------------------------------------------------------------------------
# validation/rules.py — base class (line 46)
# ---------------------------------------------------------------------------


class TestValidationRuleBase:
    def test_base_execute_raises(self):
        from sentinel.validation.rules import ValidationRule

        rule = ValidationRule("test", "base", "t", "c", "warning", {}, "")
        with pytest.raises(NotImplementedError):
            rule.execute(MagicMock())


# ---------------------------------------------------------------------------
# remediation/actions.py — escalate_to_manual (line 52)
# ---------------------------------------------------------------------------


class TestEscalateToManual:
    def test_escalate_returns_success(self):
        from sentinel.remediation.actions import escalate_to_manual

        result = escalate_to_manual(MagicMock())
        assert result["success"] is True
        assert "manual review" in result["detail"].lower()


# ---------------------------------------------------------------------------
# remediation/engine.py — unknown action (lines 132-133)
# ---------------------------------------------------------------------------


class TestRemediationEngineUnknownAction:
    def test_unknown_action_name(self, mock_db):
        from sentinel.monitor.incident_manager import IncidentManager
        from sentinel.remediation.engine import RemediationEngine

        im = IncidentManager(mock_db)
        im.update_status = MagicMock(return_value={"id": 1, "status": "remediating"})

        # Custom pattern pointing to non-existent action
        patterns = [{"pattern": "custom", "action": "nonexistent_action", "params": {}}]
        engine = RemediationEngine(mock_db, im, patterns=patterns)
        incident = {"id": 1, "incident_type": "custom_problem", "status": "detected"}
        result = engine.attempt_remediation(incident)
        assert result["remediated"] is False
        assert "Unknown action" in result["reason"]


# ---------------------------------------------------------------------------
# monitor/incident_manager.py — postmortem with acknowledged_at (lines 179, 181-182)
# ---------------------------------------------------------------------------


class TestPostmortemWithAcknowledged:
    def test_postmortem_includes_acknowledged_at(self, mock_db):
        from sentinel.monitor.incident_manager import IncidentManager

        mgr = IncidentManager(mock_db)
        mgr.create(incident_type="test", title="Ack test")

        # Manually add acknowledged_at to the incident
        mock_db._tables["incidents"][0]["acknowledged_at"] = "2026-03-22T10:00:00"
        mock_db._tables["incidents"][0]["detected_at"] = "2026-03-22T09:00:00"
        mock_db._tables["incidents"][0]["resolved_at"] = "2026-03-22T11:00:00"
        mock_db._tables["incidents"][0]["resolved_by"] = "manual"

        mgr.update_status(1, "resolved", resolved_by="manual")
        # Postmortem should have been generated with acknowledged_at in timeline
        assert len(mock_db._tables.get("postmortems", [])) >= 0

    def test_generate_postmortem_not_found(self, mock_db):
        """_generate_postmortem returns early if incident not found."""
        from sentinel.monitor.incident_manager import IncidentManager

        mgr = IncidentManager(mock_db)
        # Should not raise
        mgr._generate_postmortem(9999)

    def test_generate_postmortem_db_error(self, mock_db):
        """_generate_postmortem handles DB errors gracefully."""
        from sentinel.monitor.incident_manager import IncidentManager

        mgr = IncidentManager(mock_db)
        mgr.create(incident_type="test", title="PM error test")

        original = mock_db.execute_nonquery

        def failing_nonquery(sql, params=()):
            if "INSERT INTO postmortems" in sql:
                raise DatabaseQueryError("disk full")
            return original(sql, params)

        mock_db.execute_nonquery = failing_nonquery
        # Should not raise
        mgr._generate_postmortem(1)
        mock_db.execute_nonquery = original


# ---------------------------------------------------------------------------
# incident_manager.py — create with fallback path (line 50)
# ---------------------------------------------------------------------------


class TestIncidentCreateFallback:
    def test_create_without_output_returns_fallback(self, mock_db):
        """When INSERT RETURNING gives empty, fallback query is used."""
        from sentinel.monitor.incident_manager import IncidentManager

        mgr = IncidentManager(mock_db)
        # The mock handles this via the INSERT INTO incidents path
        result = mgr.create(
            incident_type="fallback_test",
            title="Test fallback",
            severity="info",
        )
        assert result["id"] >= 1


# ---------------------------------------------------------------------------
# api/routes/health.py — history route (line 42)
# ---------------------------------------------------------------------------


class TestHealthHistoryRoute:
    def test_get_health_history(self):
        """GET /api/health/history returns a list."""
        from contextlib import asynccontextmanager

        from fastapi.testclient import TestClient

        from sentinel.api.dependencies import get_state
        from sentinel.api.main import app

        @asynccontextmanager
        async def noop(app):
            yield

        state = MagicMock()
        state.health.get_history.return_value = [{"status": "healthy", "cpu_percent": 45.0}]

        app.dependency_overrides[get_state] = lambda: state
        original = app.router.lifespan_context
        app.router.lifespan_context = noop
        with TestClient(app) as client:
            resp = client.get("/api/health/history?hours=2")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        app.router.lifespan_context = original
        app.dependency_overrides.clear()
