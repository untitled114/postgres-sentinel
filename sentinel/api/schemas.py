"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Health ---
class HealthResponse(BaseModel):
    status: str
    sql_connected: bool
    uptime_seconds: float
    version: str = "1.0.0"
    latest_snapshot: dict[str, Any] | None = None


class SqlHealthResponse(BaseModel):
    connected: bool
    version: str | None = None
    server_name: str | None = None
    current_db: str | None = None
    server_time: str | None = None
    error: str | None = None


class HealthSnapshot(BaseModel):
    id: int | None = None
    captured_at: datetime | str | None = None
    cpu_percent: float | None = None
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    connection_count: int | None = None
    lock_wait_count: int | None = None
    long_query_count: int | None = None
    dead_tuple_ratio: float | None = None
    cache_hit_ratio: float | None = None
    avg_query_ms: float | None = None
    status: str = "unknown"
    alerts: list[dict[str, Any]] = Field(default_factory=list)


# --- Incidents ---
class IncidentCreate(BaseModel):
    incident_type: str
    title: str
    severity: Literal["info", "warning", "critical"] = "warning"
    description: str | None = None


class IncidentUpdate(BaseModel):
    status: Literal["detected", "investigating", "remediating", "resolved", "escalated"]


class IncidentResponse(BaseModel):
    id: int
    incident_type: str
    severity: str
    status: str
    title: str
    description: str | None = None
    detected_at: datetime | str | None = None
    resolved_at: datetime | str | None = None
    resolved_by: str | None = None
    dedup_key: str | None = None
    metadata: str | None = None
    acknowledged_at: datetime | str | None = None


class RemediationResponse(BaseModel):
    remediated: bool
    action: str | None = None
    detail: str | None = None
    reason: str | None = None
    escalated: bool | None = None


class PostmortemResponse(BaseModel):
    id: int | None = None
    incident_id: int
    summary: str | None = None
    root_cause: str | None = None
    timeline: str | None = None
    remediation: str | None = None
    lessons_learned: str | None = None
    generated_at: datetime | str | None = None


class SlaMetricsResponse(BaseModel):
    window_hours: int
    total_incidents: int = 0
    resolved_count: int = 0
    escalated_count: int = 0
    critical_count: int = 0
    auto_resolved_count: int = 0
    auto_remediation_rate: float | None = None
    escalation_rate: float | None = None
    avg_resolution_minutes: float | None = None
    max_resolution_minutes: float | None = None
    sla_breaches: int = 0
    sla_compliance_rate: float | None = None
    message: str | None = None


# --- Jobs ---
class JobTrigger(BaseModel):
    job_name: str


class JobInfoResponse(BaseModel):
    name: str
    schedule: str
    interval_seconds: int
    enabled: bool
    description: str | None = None
    last_run: str | None = None


class JobRunResponse(BaseModel):
    job_name: str
    status: str
    rows_affected: int | None = None
    duration_ms: int | None = None
    error: str | None = None


# --- Validation ---
class ValidationResult(BaseModel):
    rule_name: str
    rule_type: str
    passed: bool
    severity: str
    violation_count: int = 0
    description: str = ""
    table_name: str | None = None
    column_name: str | None = None
    sample_values: list[Any] = Field(default_factory=list)


class ValidationRunResponse(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[dict[str, Any]] = Field(default_factory=list)


class Scorecard(BaseModel):
    total_rules: int
    passed: int
    failed: int
    critical_failures: int
    score_percent: float
    rules: list[dict[str, Any]] = Field(default_factory=list)


# --- Chaos ---
class ChaosTrigger(BaseModel):
    scenario: str


class ChaosScenarioResponse(BaseModel):
    name: str
    description: str
    severity: str
    on_cooldown: bool = False
    cooldown_remaining_s: int = 0


class ChaosResponse(BaseModel):
    scenario: str
    triggered: bool = False
    detail: str = ""
    error: str | None = None


# --- Dashboard ---
class DashboardResponse(BaseModel):
    health: dict[str, Any] = Field(default_factory=dict)
    open_incidents: list[dict[str, Any]] = Field(default_factory=list)
    recent_incidents: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    recent_job_runs: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    chaos_scenarios: list[dict[str, Any]] = Field(default_factory=list)
    postmortems: list[dict[str, Any]] = Field(default_factory=list)
    pipeline: dict[str, Any] = Field(default_factory=dict)


# --- Governance ---
class CatalogEntry(BaseModel):
    id: int | None = None
    schema_name: str = "public"
    table_name: str
    column_name: str | None = None
    data_type: str | None = None
    description: str | None = None
    is_phi: bool = False
    is_pii: bool = False
    phi_category: str | None = None
    masking_rule: str | None = None
    retention_days: int | None = None
    classification: str = "internal"
    last_scanned_at: datetime | str | None = None


class LineageEntry(BaseModel):
    id: int | None = None
    pipeline_name: str
    execution_id: str | None = None
    source_table: str
    target_table: str
    started_at: datetime | str | None = None
    completed_at: datetime | str | None = None
    status: str = "running"
    rows_read: int | None = None
    rows_written: int | None = None
    rows_rejected: int | None = None
    error_message: str | None = None


class LineageRecordRequest(BaseModel):
    pipeline_name: str
    source_table: str
    target_table: str
    rows_read: int = 0
    rows_written: int = 0
    rows_rejected: int = 0
    status: str = "success"
    error_message: str | None = None


class PhiScanResponse(BaseModel):
    columns_scanned: int
    phi_pii_classified: int
    scanned_at: str
