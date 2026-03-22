"""Health monitoring API routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

from sentinel.api.dependencies import AppState, get_state
from sentinel.api.schemas import HealthResponse, HealthSnapshot, SqlHealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])

_start_time = time.time()


@router.get("", response_model=HealthResponse)
def get_health(state: AppState = Depends(get_state)):
    """Overall system health status."""
    sql_health = state.health.get_sql_health()
    latest = state.health.get_latest()
    return {
        "status": latest.get("status", "unknown") if latest else "initializing",
        "sql_connected": sql_health.get("connected", False),
        "uptime_seconds": round(time.time() - _start_time, 1),
        "version": "1.0.0",
        "latest_snapshot": latest,
    }


@router.get("/sql", response_model=SqlHealthResponse)
def get_sql_health(state: AppState = Depends(get_state)):
    """PostgreSQL connectivity and version info."""
    return state.health.get_sql_health()


@router.get("/history", response_model=list[HealthSnapshot])
def get_health_history(
    hours: int = Query(default=1, ge=1, le=168), state: AppState = Depends(get_state)
):
    """Health snapshot history."""
    return state.health.get_history(hours=hours)


@router.post("/snapshot", response_model=HealthSnapshot)
def capture_snapshot(state: AppState = Depends(get_state)):
    """Manually trigger a health snapshot."""
    return state.health.collect_snapshot()
