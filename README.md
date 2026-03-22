# PostgreSQL Sentinel

[![CI](https://github.com/untitled114/postgres-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/untitled114/postgres-sentinel/actions/workflows/ci.yml)

Production PostgreSQL monitoring, chaos engineering, and automated incident response. Built on TimescaleDB with a real ML pipeline domain — detects degradation, fires chaos scenarios, auto-remediates, and tracks full incident lifecycles.

Three-panel dashboard: **War Room** (live DB + pipeline health), **Training Room** (model lifecycle tracking), **Performance Room** (deployed model quality metrics).

```
┌─────────────────────────────────────────────────────────────────┐
│                       War Room                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Snapshot  │ │  Props   │ │ Feature  │ │  Active  │           │
│  │  Rate     │ │ Fresh?   │ │  Count   │ │  Model   │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                 │
│                     Training Room                               │
│  ┌──────────────────────┐ ┌──────────────────────┐              │
│  │ Last Training Run    │ │ Walk-Forward Results  │              │
│  │ ├ POINTS AUC: 0.78   │ │ ├ V4 vs V3 AUC       │              │
│  │ └ Duration: 47min    │ │ └ Fold consistency    │              │
│  └──────────────────────┘ └──────────────────────┘              │
│  ┌──────────────────────────────────────────────┐               │
│  │ Model Registry Timeline                       │               │
│  │ training → shadow → production → rolled_back  │               │
│  └──────────────────────────────────────────────┘               │
│                                                                 │
│                    Performance Room                             │
│  ┌──────────────────────┐ ┌──────────────────────┐              │
│  │ 7-Day Win Rate       │ │ Conviction Dist.     │              │
│  │ ████████░░ 62%       │ │ LOCKED ██            │              │
│  │ ──── 60% threshold   │ │ STRONG ████████      │              │
│  └──────────────────────┘ └──────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
git clone https://github.com/untitled114/postgres-sentinel.git && cd postgres-sentinel
cp .env.example .env
docker compose up -d

# Dashboard
open http://localhost:8000

# API docs
open http://localhost:8000/docs
```

> **Port conflict?** Set `SENTINEL_PORT=8080` in `.env`.

## Architecture

| Layer | Purpose | Key Files |
|-------|---------|-----------|
| **Chaos Engine** | Simulates pipeline failures | `sentinel/chaos/` |
| **Sentinel Monitor** | Polls DB health, validates data, manages incidents | `sentinel/monitor/`, `sentinel/validation/` |
| **Dashboard** | Three-panel real-time visibility | `sentinel/web/`, `sentinel/api/` |

### Tech Stack

- **PostgreSQL 16 + TimescaleDB** (Sport-Suite consolidated DB)
- **Python 3.12** with psycopg2, FastAPI, Pydantic v2
- **Vanilla HTML/CSS/JS** dark theme dashboard

## What It Monitors

### Data Pipeline Health
- Line snapshot ingestion rate (15K+/day target)
- Props freshness (`nba_props_xl` inserts within 4hrs)
- Feature count regression (must stay ≥ 102 for XL, ≥ 188 for V4)
- Book coverage (≥ 5 sportsbooks active)

### Model Quality
- 7-day rolling win rate with 60% threshold
- Calibrated probability bounds (0.35–0.95)
- Conviction distribution (LOCKED > 20% signals filter degradation)
- Model rollback detection in last 24hrs

### Pipeline Telemetry
- Per-task duration and metrics from `pipeline_runs`
- Extractor default rates from JSONB task breakdown
- Anomaly flags (zero picks, feature count regression)

## Validation Rules (11)

| Rule | Severity | What it checks |
|------|----------|---------------|
| `props_freshness` | Critical | `nba_props_xl` inserts within 4hrs |
| `line_snapshots_freshness` | Critical | Snapshots captured within 4hrs |
| `line_snapshot_volume` | Critical | 15K+ snapshots per game day |
| `book_coverage_minimum` | Warning | ≥ 5 sportsbooks in last 6hrs |
| `probability_bounds` | Critical | p_over between 0.35 and 0.95 |
| `prediction_model_version_not_null` | Critical | Every prediction has a model version |
| `feature_count_regression` | Critical | Pipeline produces ≥ 102 features |
| `conviction_distribution_check` | Warning | LOCKED ≤ 20% of daily picks |
| `model_rollback_detection` | Critical | No unexpected rollbacks in 24hrs |
| `seven_day_win_rate` | High | 7-day rolling WR ≥ 60% |

## Chaos Scenarios (9)

| Scenario | What it simulates | Severity |
|----------|------------------|----------|
| Long Running Query | pg_sleep(45) stuck query | Medium |
| Connection Flood | 20 concurrent connections | High |
| DAG Overlap | 2 concurrent pipeline_runs | Medium |
| Extractor Default Injection | Pipeline run with 0 features | High |
| Line Ingestion Drop | Deletes today's line snapshots | High |
| Model File Missing | pkl_path points to nonexistent file | High |
| Conviction Collapse | Downgrades all LOCKED → SKIP | High |
| Win Rate Crash | 7 days of 45% WR predictions | High |
| Prediction Staleness | Deletes today's predictions | Medium |

## Auto-Remediation

| Pattern | Action | Escalation |
|---------|--------|-----------|
| Blocking sessions | `kill_blocking_session` via `pg_terminate_backend` | Manual if system session |
| Stale connections | `cleanup_stale_sessions` | Manual on permission error |
| Failed pipeline | `trigger_pipeline_refresh` | Manual after retry |
| Missing line data | `trigger_line_refresh` | Manual on persistent failure |

## Database Tables Monitored

| Schema | Table | What Sentinel watches |
|--------|-------|-----------------------|
| `intelligence` | `nba_props_xl` | Write volume, freshness (3.7M rows) |
| `intelligence` | `nba_line_snapshots` | Snapshot ingestion rate (15K+/day) |
| `axiom` | `nba_prediction_history` | Prediction quality, win rate |
| `axiom` | `axiom_conviction` | Conviction distribution |
| `axiom` | `pipeline_runs` | DAG health, feature counts |
| `axiom` | `model_registry` | Model lifecycle, rollbacks |
| `axiom` | `validation_runs` | Walk-forward results |

## Development

```bash
make test          # 201 tests
make fmt           # black + isort
make lint          # flake8
make reset         # destroy + rebuild
make status        # system health check
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | DB health metrics |
| `/api/incidents` | GET | Open incidents list |
| `/api/incidents/{id}` | PATCH | Update incident status |
| `/api/validation/run` | POST | Trigger validation rules |
| `/api/chaos/trigger` | POST | Trigger chaos scenario |
| `/api/chaos/scenarios` | GET | List available scenarios |
| `/api/training/latest` | GET | Last training run |
| `/api/training/registry` | GET | Model registry timeline |
| `/api/performance/win-rate` | GET | 7-day rolling WR |
| `/api/performance/conviction` | GET | Today's conviction distribution |
