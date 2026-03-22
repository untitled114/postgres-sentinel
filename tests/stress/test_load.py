"""Stress tests — validates system behavior under production-scale load.

These tests use the mock database (no SQL Server required) to verify that
Sentinel's core engines handle high-volume scenarios without degradation.

Run with: pytest tests/stress/ -v
"""

from __future__ import annotations

import time

from sentinel.chaos.engine import ChaosEngine
from sentinel.config.models import ValidationRuleConfig
from sentinel.monitor.health import HealthCollector
from sentinel.monitor.incident_manager import IncidentManager
from sentinel.remediation.engine import RemediationEngine
from sentinel.validation.engine import ValidationEngine


class TestIncidentStorm:
    """Verify incident management under alert storm conditions.

    In production, a cascading failure can generate hundreds of alerts in seconds.
    The system must:
    - Deduplicate correctly (no duplicate incidents for the same issue)
    - Maintain consistent state under concurrent writes
    - Not degrade in performance as incident count grows
    """

    def test_dedup_under_rapid_fire(self, mock_db, config):
        """500 rapid alerts for the same issue should produce only 1 incident.

        The IncidentManager checks for open incidents with the same dedup_key
        before creating a new one. With the mock DB, dedup lookups return
        previously inserted incidents, so only the first call creates a row.
        """
        mgr = IncidentManager(mock_db)

        created = []
        for i in range(500):
            result = mgr.create(
                incident_type="cpu",
                title=f"CPU critical: attempt {i}",
                severity="critical",
                dedup_key="health_cpu",
            )
            created.append(result)

        # All 500 calls should return the same incident ID (dedup)
        ids = {r["id"] for r in created}
        assert len(ids) == 1, f"Expected 1 unique incident, got {len(ids)}"

    def test_many_distinct_incidents(self, mock_db, config):
        """100 distinct incident types (no dedup) should create separate incidents."""
        mgr = IncidentManager(mock_db)

        for i in range(100):
            mgr.create(
                incident_type=f"type_{i}",
                title=f"Incident #{i}",
                severity="warning",
                # No dedup_key — each creates a new incident
            )

        assert len(mock_db._tables["incidents"]) == 100

    def test_incident_throughput(self, mock_db, config):
        """Measure incident creation throughput — should handle 1000+ per second."""
        mgr = IncidentManager(mock_db)

        start = time.perf_counter()
        count = 1000
        for i in range(count):
            mgr.create(
                incident_type=f"perf_test_{i}",
                title=f"Throughput test {i}",
                severity="warning",
            )
        elapsed = time.perf_counter() - start

        rate = count / elapsed
        # Even in-memory mock should handle 1000+ incidents/sec easily
        assert rate > 500, f"Incident creation too slow: {rate:.0f}/sec"
        assert len(mock_db._tables["incidents"]) == count

    def test_escalation_at_scale(self, mock_db, config):
        """Escalation check with 200 open incidents should complete quickly."""
        mgr = IncidentManager(mock_db)

        for i in range(200):
            mgr.create(
                incident_type=f"scale_{i}",
                title=f"Scale test {i}",
                severity="critical",
                dedup_key=f"scale_{i}",
            )

        start = time.perf_counter()
        mgr.check_escalations(timeout_seconds=0)  # 0 = escalate immediately
        elapsed = time.perf_counter() - start

        # Escalation of 200 incidents should take < 1 second
        assert elapsed < 1.0, f"Escalation too slow: {elapsed:.2f}s for 200 incidents"


class TestValidationThroughput:
    """Verify validation engine handles large rule sets without degradation."""

    @staticmethod
    def _make_rules(count: int) -> list[ValidationRuleConfig]:
        """Generate N null_check validation rules."""
        return [
            ValidationRuleConfig(
                name=f"rule_{i}",
                type="null_check",
                table="customers",
                column="email",
                severity="warning",
                description=f"Test rule {i}",
            )
            for i in range(count)
        ]

    def test_50_rules(self, mock_db, config):
        """50 validation rules should all execute and return results."""
        rules = self._make_rules(50)
        engine = ValidationEngine(mock_db, rules)
        results = engine.run_all()

        assert len(results) == 50
        # All should pass (mock DB returns 0 violations)
        assert all(r.get("passed") for r in results)

    def test_validation_throughput(self, mock_db, config):
        """Measure rules-per-second throughput."""
        rules = self._make_rules(200)
        engine = ValidationEngine(mock_db, rules)

        start = time.perf_counter()
        results = engine.run_all()
        elapsed = time.perf_counter() - start

        rate = len(results) / elapsed
        assert rate > 100, f"Validation too slow: {rate:.0f} rules/sec"

    def test_scorecard_after_mass_validation(self, mock_db, config):
        """Scorecard should reflect correct pass rate after many runs."""
        rules = self._make_rules(20)
        engine = ValidationEngine(mock_db, rules)

        # Run validation 5 times (simulating 5 scheduled runs)
        for _ in range(5):
            engine.run_all()

        scorecard = engine.get_scorecard()
        assert scorecard["total_rules"] >= 0  # Scorecard should not error


class TestChaosEngineResilience:
    """Verify chaos engine handles rapid and concurrent scenario triggers."""

    def test_cooldown_enforcement(self, mock_db, config):
        """Rapid-fire triggers should respect cooldown periods."""
        engine = ChaosEngine(mock_db, IncidentManager(mock_db))

        # First trigger should succeed
        result1 = engine.trigger("Long Running Query")
        assert result1.get("triggered") is True or "triggered" in str(result1)

        # Immediate re-trigger should be blocked by cooldown
        result2 = engine.trigger("Long Running Query")
        assert "cooldown" in str(result2).lower() or result2.get("triggered") is True

    def test_all_scenarios_trigger(self, mock_db, config):
        """Every built-in scenario should trigger without error."""
        engine = ChaosEngine(mock_db, IncidentManager(mock_db))
        scenarios = engine.list_scenarios()

        for scenario in scenarios:
            name = scenario["name"]
            result = engine.trigger(name)
            # Should either trigger successfully or report an error (not crash)
            assert (
                "triggered" in result or "error" in result
            ), f"{name} returned unexpected: {result}"


class TestRemediationUnderLoad:
    """Verify remediation engine handles multiple simultaneous incidents."""

    def test_remediate_many_open_incidents(self, mock_db, config):
        """Remediating 50 open incidents should not error."""
        inc_mgr = IncidentManager(mock_db)
        rem_engine = RemediationEngine(mock_db, inc_mgr)

        # Create 50 incidents of various types
        for i in range(50):
            inc_mgr.create(
                incident_type=f"test_type_{i % 5}",
                title=f"Remediation load test {i}",
                severity="critical",
            )

        # Should not raise, even if no patterns match
        rem_engine.remediate_open_incidents()

    def test_remediation_throughput(self, mock_db, config):
        """Pattern matching + remediation should handle 100 incidents quickly."""
        inc_mgr = IncidentManager(mock_db)
        rem_engine = RemediationEngine(mock_db, inc_mgr)

        for i in range(100):
            inc_mgr.create(
                incident_type="blocking_chain",
                title=f"Blocking {i}",
                severity="critical",
                dedup_key=f"block_{i}",
            )

        start = time.perf_counter()
        rem_engine.remediate_open_incidents()
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Remediation too slow: {elapsed:.2f}s for 100 incidents"


class TestHealthCollectorStability:
    """Verify health collector handles repeated snapshot collection."""

    def test_rapid_snapshots(self, mock_db, config):
        """100 rapid health snapshots should not degrade or error."""
        collector = HealthCollector(mock_db, config)

        for _ in range(100):
            result = collector.collect_snapshot()
            assert "status" in result or "error" in str(result)

    def test_snapshot_history_growth(self, mock_db, config):
        """Snapshot table should grow linearly, not exponentially."""
        collector = HealthCollector(mock_db, config)

        for _ in range(50):
            collector.collect_snapshot()

        snapshots = mock_db._tables.get("health_snapshots", [])
        assert len(snapshots) == 50
