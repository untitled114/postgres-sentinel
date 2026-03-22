"""Tests for PipelineMonitor — Sport-suite metrics collection and threshold evaluation."""

from __future__ import annotations

import pytest

from sentinel.config.models import ThresholdConfig
from sentinel.monitor.pipeline import PipelineMonitor


class TestPipelineMonitorCollect:
    """Test metrics collection from Sport-suite tables."""

    def test_collect_metrics_returns_dict(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        assert isinstance(metrics, dict)

    def test_collect_metrics_has_win_rate(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        assert "win_rate_7d" in metrics

    def test_collect_metrics_has_predictions_today(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        assert "predictions_today" in metrics

    def test_collect_metrics_has_line_snapshots(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        assert "line_snapshots_today" in metrics

    def test_collect_metrics_has_conviction_distribution(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        assert "conviction_distribution" in metrics

    def test_collect_metrics_caches_latest(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        assert monitor.get_latest_metrics() is None
        monitor.collect_metrics()
        assert monitor.get_latest_metrics() is not None

    def test_collect_metrics_handles_db_error(self, mock_db):
        """Should return defaults if DB queries fail."""
        from sentinel.core.exceptions import DatabaseQueryError

        original = mock_db.execute_query

        def failing_query(sql, params=()):
            raise DatabaseQueryError("connection lost")

        mock_db.execute_query = failing_query
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        assert isinstance(metrics, dict)
        # Restore
        mock_db.execute_query = original


class TestPipelineMonitorThresholds:
    """Test threshold evaluation for pipeline metrics."""

    def test_no_alerts_when_healthy(self, mock_db):
        thresholds = ThresholdConfig(
            win_rate_7d_warning=55.0,
            win_rate_7d_critical=50.0,
            line_snapshot_volume_warning=10000,
            line_snapshot_volume_critical=5000,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = monitor.collect_metrics()
        alerts = monitor.evaluate_thresholds(metrics)
        # Default mock returns 58.5% win rate and 12500 snapshots - both healthy
        win_alerts = [a for a in alerts if a["metric"] == "win_rate_7d"]
        snapshot_alerts = [a for a in alerts if a["metric"] == "line_snapshot_volume"]
        assert len(win_alerts) == 0
        assert len(snapshot_alerts) == 0

    def test_win_rate_warning_alert(self, mock_db):
        """Win rate at 52% should trigger warning but not critical."""
        thresholds = ThresholdConfig(
            win_rate_7d_warning=55.0,
            win_rate_7d_critical=50.0,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {"win_rate_7d": 52.0, "predictions_today": 10, "line_snapshots_today": 15000}
        alerts = monitor.evaluate_thresholds(metrics)
        wr_alerts = [a for a in alerts if a["metric"] == "win_rate_7d"]
        assert len(wr_alerts) == 1
        assert wr_alerts[0]["level"] == "warning"

    def test_win_rate_critical_alert(self, mock_db):
        """Win rate at 48% should trigger critical."""
        thresholds = ThresholdConfig(
            win_rate_7d_warning=55.0,
            win_rate_7d_critical=50.0,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {"win_rate_7d": 48.0, "predictions_today": 10, "line_snapshots_today": 15000}
        alerts = monitor.evaluate_thresholds(metrics)
        wr_alerts = [a for a in alerts if a["metric"] == "win_rate_7d"]
        assert len(wr_alerts) == 1
        assert wr_alerts[0]["level"] == "critical"

    def test_line_snapshot_volume_alert(self, mock_db):
        """Low snapshot volume should trigger alert."""
        thresholds = ThresholdConfig(
            line_snapshot_volume_warning=10000,
            line_snapshot_volume_critical=5000,
        )
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {"win_rate_7d": 60.0, "predictions_today": 10, "line_snapshots_today": 3000}
        alerts = monitor.evaluate_thresholds(metrics)
        snap_alerts = [a for a in alerts if a["metric"] == "line_snapshot_volume"]
        assert len(snap_alerts) == 1
        assert snap_alerts[0]["level"] == "critical"

    def test_evaluate_returns_list(self, mock_db):
        monitor = PipelineMonitor(mock_db, ThresholdConfig())
        metrics = monitor.collect_metrics()
        alerts = monitor.evaluate_thresholds(metrics)
        assert isinstance(alerts, list)

    def test_alert_has_required_fields(self, mock_db):
        thresholds = ThresholdConfig(win_rate_7d_warning=99.0, win_rate_7d_critical=98.0)
        monitor = PipelineMonitor(mock_db, thresholds)
        metrics = {"win_rate_7d": 58.5, "predictions_today": 0, "line_snapshots_today": 0}
        alerts = monitor.evaluate_thresholds(metrics)
        wr_alerts = [a for a in alerts if a["metric"] == "win_rate_7d"]
        if wr_alerts:
            alert = wr_alerts[0]
            assert "metric" in alert
            assert "level" in alert
            assert "value" in alert
            assert "threshold" in alert
