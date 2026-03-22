"""Performance Room API — production model health."""

from __future__ import annotations

import logging
from datetime import datetime

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/performance", tags=["performance"])

_DB_OPTS = {
    "host": "localhost",
    "port": 5500,
    "dbname": "sportsuite",
    "user": "mlb_user",
    "password": "mlb_secure_2025",
    "connect_timeout": 5,
}


def _query(sql: str, params: tuple = (), schema: str = "axiom") -> list[dict]:
    opts = {**_DB_OPTS, "options": f"-c search_path={schema},public"}
    try:
        conn = psycopg2.connect(**opts)
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("Performance query failed: %s", e)
        return []


@router.get("/win-rate")
def get_win_rate(days: int = Query(default=7, ge=1, le=90)):
    """Daily win rate for the last N days."""
    rows = _query(
        """
        SELECT run_date,
               COUNT(*) AS total,
               SUM(CASE WHEN is_hit = TRUE THEN 1 ELSE 0 END) AS wins,
               ROUND(
                   SUM(CASE WHEN is_hit = TRUE THEN 1 ELSE 0 END)::numeric
                   / NULLIF(COUNT(*), 0) * 100, 1
               ) AS win_rate
        FROM nba_prediction_history
        WHERE is_hit IS NOT NULL
          AND run_date >= CURRENT_DATE - %s * INTERVAL '1 day'
        GROUP BY run_date
        ORDER BY run_date
        """,
        (days,),
    )

    # Compute rolling aggregate
    total_picks = sum(r.get("total", 0) for r in rows)
    total_wins = sum(r.get("wins", 0) for r in rows)
    rolling_wr = round(total_wins / total_picks * 100, 1) if total_picks > 0 else 0

    return {
        "days": days,
        "daily": rows,
        "rolling_win_rate": rolling_wr,
        "total_picks": total_picks,
        "total_wins": total_wins,
    }


@router.get("/conviction")
def get_conviction():
    """Today's conviction distribution."""
    rows = _query("""
        SELECT conviction_label, COUNT(*) AS count,
               ROUND(AVG(conviction)::numeric, 3) AS avg_conviction
        FROM axiom_conviction
        WHERE run_date = CURRENT_DATE
        GROUP BY conviction_label
        ORDER BY avg_conviction DESC
        """)

    # Map to expected labels with defaults
    dist = {"LOCKED": 0, "STRONG": 0, "WATCH": 0, "SKIP": 0}
    for r in rows:
        label = r.get("conviction_label", "").upper()
        if label in dist:
            dist[label] = r.get("count", 0)

    return {"date": datetime.now().strftime("%Y-%m-%d"), "distribution": dist, "raw": rows}


@router.get("/summary")
def get_summary():
    """Rollback status, prediction volume, anomalies."""
    # Last rollback
    rollbacks = _query("""
        SELECT model_version, market, rolled_back_at, rollback_reason
        FROM validation_runs
        WHERE rolled_back = TRUE
        ORDER BY rolled_back_at DESC
        LIMIT 1
        """)

    # 14-day prediction volume
    volume = _query("""
        SELECT run_date, COUNT(*) AS picks
        FROM nba_prediction_history
        WHERE run_date >= CURRENT_DATE - INTERVAL '14 days'
        GROUP BY run_date
        ORDER BY run_date
        """)

    # Today's props + snapshots
    props_today = _query(
        "SELECT COUNT(*) AS cnt FROM nba_props_xl WHERE game_date = CURRENT_DATE",
        schema="intelligence",
    )

    snapshots_today = _query(
        "SELECT COUNT(*) AS cnt FROM nba_line_snapshots WHERE game_date = CURRENT_DATE",
        schema="intelligence",
    )

    # Latest pipeline run
    latest_run = _query("""
        SELECT run_id, status, summary, started_at
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 1
        """)

    feature_count = None
    if latest_run:
        summary = latest_run[0].get("summary") or {}
        if isinstance(summary, str):
            import json

            summary = json.loads(summary)
        feature_count = summary.get("feature_count")

    return {
        "last_rollback": rollbacks[0] if rollbacks else None,
        "volume_14d": volume,
        "props_today": props_today[0]["cnt"] if props_today else 0,
        "snapshots_today": snapshots_today[0]["cnt"] if snapshots_today else 0,
        "feature_count": feature_count,
        "latest_run": latest_run[0] if latest_run else None,
    }
