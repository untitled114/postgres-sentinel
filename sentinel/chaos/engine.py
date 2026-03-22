"""Chaos engine — triggers scenarios, manages cooldowns."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from sentinel.chaos.scenarios import BUILTIN_SCENARIOS, ChaosScenario
from sentinel.config.models import ChaosScenarioConfig
from sentinel.db.connection import ConnectionManager
from sentinel.monitor.incident_manager import IncidentManager

logger = logging.getLogger(__name__)


class ChaosEngine:
    """Manages and triggers chaos scenarios."""

    def __init__(
        self,
        db: ConnectionManager,
        incident_manager: IncidentManager,
        scenarios: list[ChaosScenarioConfig] | None = None,
    ):
        self.db = db
        self.incident_manager = incident_manager
        self._cooldowns: dict[str, float] = {}
        self._scenarios: dict[str, ChaosScenario] = {}

        # Register built-in scenarios
        for name, cls in BUILTIN_SCENARIOS.items():
            self._scenarios[name] = cls()

    def list_scenarios(self) -> list[dict[str, Any]]:
        """List all available chaos scenarios."""
        now = time.time()
        result = []
        for name, scenario in self._scenarios.items():
            cooldown_until = self._cooldowns.get(name, 0)
            result.append(
                {
                    "name": name,
                    "description": scenario.description,
                    "severity": scenario.severity,
                    "on_cooldown": now < cooldown_until,
                    "cooldown_remaining_s": max(0, int(cooldown_until - now)),
                }
            )
        return result

    def trigger(self, scenario_name: str) -> dict[str, Any]:
        """Trigger a specific chaos scenario by name."""
        scenario = self._scenarios.get(scenario_name)
        if not scenario:
            return {
                "error": f"Unknown scenario: {scenario_name}",
                "available": list(self._scenarios.keys()),
            }

        # Check cooldown
        now = time.time()
        cooldown_until = self._cooldowns.get(scenario_name, 0)
        if now < cooldown_until:
            remaining = int(cooldown_until - now)
            return {"error": f"Scenario on cooldown for {remaining}s", "scenario": scenario_name}

        logger.info("Triggering chaos: %s", scenario_name)
        result = scenario.execute(self.db)

        # Set cooldown
        self._cooldowns[scenario_name] = now + 30

        # Create incident — map scenario severity to DB-valid values
        severity_map = {"high": "critical", "medium": "warning", "low": "info"}
        db_severity = severity_map.get(scenario.severity, scenario.severity)
        if result.get("triggered"):
            self.incident_manager.create(
                incident_type=f"chaos:{scenario_name.lower().replace(' ', '_')}",
                title=f"Chaos: {scenario_name}",
                severity=db_severity,
                description=result.get("detail", ""),
                dedup_key=f"chaos_{scenario_name}",
                metadata={"chaos_scenario": scenario_name, "result": result},
            )

        return {"scenario": scenario_name, **result}

    def trigger_random(self) -> dict[str, Any]:
        """Trigger a random non-cooldown scenario."""
        now = time.time()
        available = [
            name
            for name, scenario in self._scenarios.items()
            if now >= self._cooldowns.get(name, 0)
        ]
        if not available:
            return {"error": "All scenarios on cooldown"}

        chosen = random.choice(available)
        return self.trigger(chosen)
