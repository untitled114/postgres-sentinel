"""Governance API routes — data catalog, sensitive data classification, lineage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from sentinel.api.dependencies import get_state
from sentinel.api.schemas import (
    CatalogEntry,
    LineageEntry,
    LineageRecordRequest,
    PhiScanResponse,
)

router = APIRouter(prefix="/api/governance", tags=["governance"])


@router.get("/catalog", response_model=list[CatalogEntry])
def get_catalog(
    table: str | None = Query(None, description="Filter by table name"),
    state=Depends(get_state),
):
    """Browse the data catalog."""
    rows = state.catalog.get_catalog(table_name=table)
    return rows


@router.get("/catalog/sensitive", response_model=list[CatalogEntry])
def get_sensitive_columns(state=Depends(get_state)):
    """List all columns classified as sensitive (PHI/PII/credentials)."""
    rows = state.catalog.get_catalog(phi_only=True)
    return rows


@router.post("/catalog/scan", response_model=PhiScanResponse)
def scan_schema(
    schema_name: str = Query("public", description="Schema to scan"),
    state=Depends(get_state),
):
    """Trigger a schema scan to auto-classify sensitive columns."""
    result = state.catalog.scan_schema(schema_name=schema_name)
    return result


@router.get("/lineage", response_model=list[LineageEntry])
def get_lineage(
    pipeline: str | None = Query(None, description="Filter by pipeline name"),
    limit: int = Query(50, ge=1, le=500),
    state=Depends(get_state),
):
    """View ETL lineage records."""
    rows = state.catalog.get_lineage(pipeline_name=pipeline, limit=limit)
    return rows


@router.post("/lineage", response_model=dict)
def record_lineage(req: LineageRecordRequest, state=Depends(get_state)):
    """Record an ETL lineage entry."""
    lineage_id = state.catalog.record_lineage(
        pipeline_name=req.pipeline_name,
        source_table=req.source_table,
        target_table=req.target_table,
        rows_read=req.rows_read,
        rows_written=req.rows_written,
        rows_rejected=req.rows_rejected,
        status=req.status,
        error_message=req.error_message,
    )
    return {"id": lineage_id, "status": "recorded"}
