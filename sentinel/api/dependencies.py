"""Dependency injection for shared engine instances."""

from __future__ import annotations

from sentinel.chaos.engine import ChaosEngine
from sentinel.config.loader import load_config
from sentinel.config.models import SentinelConfig
from sentinel.db.connection import ConnectionManager
from sentinel.governance.catalog import DataCatalogEngine
from sentinel.jobs.runner import JobRunner
from sentinel.monitor.blocker_detector import BlockerDetector
from sentinel.monitor.health import HealthCollector
from sentinel.monitor.incident_manager import IncidentManager
from sentinel.monitor.pipeline import PipelineMonitor
from sentinel.remediation.engine import RemediationEngine
from sentinel.validation.engine import ValidationEngine


class AppState:
    """Holds all shared engine instances."""

    def __init__(self):
        self.config: SentinelConfig = load_config()
        self.db: ConnectionManager = ConnectionManager(self.config.database)
        self.health: HealthCollector = HealthCollector(self.db, self.config)
        self.blocker: BlockerDetector = BlockerDetector(self.db)
        self.incidents: IncidentManager = IncidentManager(self.db)
        self.validation: ValidationEngine = ValidationEngine(self.db, self.config.validation_rules)
        self.jobs: JobRunner = JobRunner(self.db, self.config.jobs)
        self.chaos: ChaosEngine = ChaosEngine(self.db, self.incidents)
        self.remediation: RemediationEngine = RemediationEngine(self.db, self.incidents)
        self.catalog: DataCatalogEngine = DataCatalogEngine(self.db)
        self.pipeline: PipelineMonitor = PipelineMonitor(self.db, self.config.thresholds)


# Singleton
_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state


def reset_state() -> None:
    """Reset state (for testing)."""
    global _state
    _state = None
