"""Tests for AppState, get_state singleton, and reset_state."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sentinel.api.dependencies import AppState, get_state, reset_state


class TestResetState:
    def test_reset_clears_singleton(self):
        """reset_state() sets _state to None so next get_state() creates fresh."""
        reset_state()
        import sentinel.api.dependencies as deps

        assert deps._state is None

    def test_get_state_after_reset_creates_new(self):
        """get_state() after reset creates a new AppState (with mocked deps)."""
        reset_state()

        mock_config = MagicMock()
        mock_config.database = MagicMock()
        mock_config.thresholds = MagicMock()
        mock_config.validation_rules = []
        mock_config.jobs = []

        with (
            patch("sentinel.api.dependencies.load_config", return_value=mock_config),
            patch("sentinel.api.dependencies.ConnectionManager"),
            patch("sentinel.api.dependencies.HealthCollector"),
            patch("sentinel.api.dependencies.BlockerDetector"),
            patch("sentinel.api.dependencies.IncidentManager"),
            patch("sentinel.api.dependencies.ValidationEngine"),
            patch("sentinel.api.dependencies.JobRunner"),
            patch("sentinel.api.dependencies.ChaosEngine"),
            patch("sentinel.api.dependencies.RemediationEngine"),
            patch("sentinel.api.dependencies.DataCatalogEngine"),
            patch("sentinel.api.dependencies.PipelineMonitor"),
        ):
            state = get_state()
            assert state is not None
            assert state.config is mock_config

            # Second call returns same instance (singleton)
            state2 = get_state()
            assert state2 is state

        # Clean up
        reset_state()


class TestAppStateInit:
    def test_wires_all_engines(self):
        """AppState.__init__ instantiates all engines."""
        mock_config = MagicMock()
        mock_config.database = MagicMock()
        mock_config.thresholds = MagicMock()
        mock_config.validation_rules = []
        mock_config.jobs = []

        with (
            patch("sentinel.api.dependencies.load_config", return_value=mock_config),
            patch("sentinel.api.dependencies.ConnectionManager") as MockConn,
            patch("sentinel.api.dependencies.HealthCollector") as MockHealth,
            patch("sentinel.api.dependencies.BlockerDetector") as MockBlocker,
            patch("sentinel.api.dependencies.IncidentManager") as MockIncidents,
            patch("sentinel.api.dependencies.ValidationEngine") as MockValidation,
            patch("sentinel.api.dependencies.JobRunner") as MockJobs,
            patch("sentinel.api.dependencies.ChaosEngine") as MockChaos,
            patch("sentinel.api.dependencies.RemediationEngine") as MockRemediation,
            patch("sentinel.api.dependencies.DataCatalogEngine") as MockCatalog,
            patch("sentinel.api.dependencies.PipelineMonitor") as MockPipeline,
        ):
            state = AppState()

            assert state.config is mock_config
            MockConn.assert_called_once_with(mock_config.database)
            MockHealth.assert_called_once()
            MockBlocker.assert_called_once()
            MockIncidents.assert_called_once()
            MockValidation.assert_called_once()
            MockJobs.assert_called_once()
            MockChaos.assert_called_once()
            MockRemediation.assert_called_once()
            MockCatalog.assert_called_once()
            MockPipeline.assert_called_once()
