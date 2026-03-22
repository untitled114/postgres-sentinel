"""Training Room API — model lifecycle visibility."""

from __future__ import annotations

import logging

import psycopg2
import psycopg2.extras
from fastapi import APIRouter

from sentinel.config.loader import load_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/training", tags=["training"])


def _get_conn():
    cfg = load_config().database
    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.name,
        user=cfg.user,
        password=cfg.password,
        options="-c search_path=axiom,public",
        connect_timeout=cfg.connect_timeout,
    )
    conn.autocommit = True
    return conn


def _query(sql: str, params: tuple = ()) -> list[dict]:
    try:
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("Training query failed: %s", e)
        return []


@router.get("/latest")
def get_latest_training():
    """Last training run + extractor report from pipeline_runs."""
    runs = _query("""
        SELECT run_id, run_date, run_type, started_at, ended_at, status,
               duration_ms, tasks, summary
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 1
        """)

    if not runs:
        return {"run": None, "extractors": []}

    run = runs[0]
    extractors = []
    tasks = run.get("tasks") or []
    if isinstance(tasks, str):
        import json

        tasks = json.loads(tasks)

    for task in tasks:
        if task.get("metrics"):
            extractors.append(
                {
                    "name": task.get("name", "unknown"),
                    "status": task.get("status", "unknown"),
                    "duration_ms": task.get("duration_ms"),
                    "metrics": task.get("metrics", {}),
                }
            )

    return {"run": run, "extractors": extractors}


@router.get("/validations")
def get_validations():
    """Walk-forward validation results."""
    rows = _query("""
        SELECT id, model_version, market, run_date, auc_mean, auc_std,
               wr_mean, roi_mean, fold_count, beats_baseline
        FROM validation_runs
        ORDER BY run_date DESC
        LIMIT 20
        """)
    return {"validations": rows}


@router.get("/registry")
def get_registry():
    """Model registry timeline."""
    registry = _query("""
        SELECT version, market, status, auc, r2, feature_count,
               pkl_path, promoted_at, rolled_back_at, created_at
        FROM model_registry
        ORDER BY created_at DESC
        """)

    return {"models": registry}
