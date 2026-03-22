"""Incident management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from sentinel.api.dependencies import AppState, get_state
from sentinel.api.schemas import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
    PostmortemResponse,
    RemediationResponse,
    SlaMetricsResponse,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    limit: int = Query(default=20, ge=1, le=100), state: AppState = Depends(get_state)
):
    """List recent incidents."""
    return state.incidents.list_recent(limit=limit)


@router.get("/open", response_model=list[IncidentResponse])
def list_open_incidents(state: AppState = Depends(get_state)):
    """List all open (non-resolved) incidents."""
    return state.incidents.list_open()


@router.get("/postmortems/recent", response_model=list[PostmortemResponse])
def list_postmortems(limit: int = 10, state: AppState = Depends(get_state)):
    """List recent postmortems."""
    return state.incidents.list_postmortems(limit=limit)


@router.get("/metrics/sla", response_model=SlaMetricsResponse)
def get_sla_metrics(
    hours: int = Query(default=24, ge=1, le=720), state: AppState = Depends(get_state)
):
    """SLA compliance metrics for the given time window.

    Returns:
        - Total incidents in window
        - Mean/median/max time to resolve (minutes)
        - Auto-remediation rate
        - Escalation rate
        - SLA breach count (critical > 60 min, warning > 4 hrs)
    """
    rows = state.db.execute_query(
        "SELECT * FROM incidents WHERE detected_at >= NOW() - INTERVAL '%s hours'",
        (hours,),
    )

    total = len(rows)
    if total == 0:
        return {"total_incidents": 0, "window_hours": hours, "message": "No incidents in window"}

    resolved = [r for r in rows if r.get("resolved_at") and r.get("detected_at")]
    escalated = [r for r in rows if r.get("status") == "escalated"]
    auto_resolved = [r for r in resolved if r.get("resolved_by") == "auto"]
    critical = [r for r in rows if r.get("severity") == "critical"]

    # Compute resolution times in minutes
    resolution_mins = []
    for r in resolved:
        try:
            detected = r["detected_at"]
            res = r["resolved_at"]
            if hasattr(detected, "timestamp") and hasattr(res, "timestamp"):
                delta = (res - detected).total_seconds() / 60.0
                resolution_mins.append(delta)
        except (TypeError, AttributeError):
            continue

    avg_resolution = sum(resolution_mins) / len(resolution_mins) if resolution_mins else None
    max_resolution = max(resolution_mins) if resolution_mins else None

    # SLA breaches: critical > 60 min, warning > 240 min
    breaches = 0
    for r in resolved:
        try:
            delta_min = (r["resolved_at"] - r["detected_at"]).total_seconds() / 60.0
            if r.get("severity") == "critical" and delta_min > 60:
                breaches += 1
            elif r.get("severity") == "warning" and delta_min > 240:
                breaches += 1
        except (TypeError, AttributeError):
            continue

    return {
        "window_hours": hours,
        "total_incidents": total,
        "resolved_count": len(resolved),
        "escalated_count": len(escalated),
        "critical_count": len(critical),
        "auto_resolved_count": len(auto_resolved),
        "auto_remediation_rate": round(len(auto_resolved) / max(len(resolved), 1) * 100, 1),
        "escalation_rate": round(len(escalated) / max(total, 1) * 100, 1),
        "avg_resolution_minutes": round(avg_resolution, 1) if avg_resolution else None,
        "max_resolution_minutes": round(max_resolution, 1) if max_resolution else None,
        "sla_breaches": breaches,
        "sla_compliance_rate": (
            round((1 - breaches / max(len(resolved), 1)) * 100, 1) if resolved else None
        ),
    }


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, state: AppState = Depends(get_state)):
    """Get a single incident by ID."""
    incident = state.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("", response_model=IncidentResponse)
def create_incident(body: IncidentCreate, state: AppState = Depends(get_state)):
    """Manually create an incident."""
    return state.incidents.create(
        incident_type=body.incident_type,
        title=body.title,
        severity=body.severity,
        description=body.description,
    )


@router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: int, body: IncidentUpdate, state: AppState = Depends(get_state)):
    """Update incident status (acknowledge, resolve, escalate)."""
    try:
        return state.incidents.update_status(incident_id, body.status, resolved_by="manual")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{incident_id}/remediate", response_model=RemediationResponse)
def remediate_incident(incident_id: int, state: AppState = Depends(get_state)):
    """Attempt auto-remediation on a specific incident."""
    incident = state.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return state.remediation.attempt_remediation(incident)


@router.get("/{incident_id}/postmortem", response_model=PostmortemResponse)
def get_postmortem(incident_id: int, state: AppState = Depends(get_state)):
    """Get the postmortem for a resolved incident."""
    pm = state.incidents.get_postmortem(incident_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Postmortem not found")
    return pm
