"""Sentinel exception hierarchy for precise error handling."""


class SentinelError(Exception):
    """Base exception for all Sentinel errors."""


class DatabaseConnectionError(SentinelError):
    """Failed to establish a database connection."""


class DatabaseQueryError(SentinelError):
    """A SQL query or function call failed."""


class DatabaseTimeoutError(DatabaseQueryError):
    """A query exceeded its timeout."""


class RemediationError(SentinelError):
    """A remediation action failed to execute."""


class ValidationRuleError(SentinelError):
    """A validation rule failed to execute (not a rule violation — an execution error)."""


class ChaosScenarioError(SentinelError):
    """A chaos scenario failed to trigger."""


class ConfigurationError(SentinelError):
    """Invalid or missing configuration."""
