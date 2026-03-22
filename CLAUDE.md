# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PostgreSQL Sentinel** — Production PostgreSQL monitoring, chaos engineering, and automated incident response. Three-panel dashboard: War Room (live health), Training Room (model lifecycle), Performance Room (deployed model quality). Monitors a TimescaleDB instance with 6 schemas across an ML pipeline domain.

Tech stack: Python 3.12, FastAPI, psycopg2, PostgreSQL 16 + TimescaleDB, Pydantic v2, vanilla JS dashboard.

## Commands

```bash
# Start everything (SQL Server + schema init + Sentinel app)
docker compose up -d
# Dashboard: http://localhost:8000  |  Swagger: http://localhost:8000/docs

# Run all tests (149 tests, 82% coverage; 70% minimum enforced in pyproject.toml)
pytest tests/ -v --cov=sentinel --cov-report=term-missing

# Run single test file / single test
pytest tests/unit/test_health.py -v
pytest tests/unit/test_health.py::test_function_name -v

# Format
isort sentinel/ tests/ && black sentinel/ tests/

# Lint
flake8 sentinel/ tests/ --max-line-length=100 --ignore=E203,W503,B008
isort --check-only sentinel/ tests/
black --check sentinel/ tests/

# Full reset (destroys data volumes)
docker compose down -v && docker compose up -d --build

# SQL shell into SentinelDB
docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P '<SA_PASSWORD>' -d SentinelDB -C
```

All also available as Makefile targets: `make up`, `make down`, `make build`, `make reset`, `make test`, `make fmt`, `make lint`, `make logs`, `make shell-db`, `make chaos-random`, `make validate`, `make status`.

Note: Local `.env` may set `SENTINEL_PORT=8080` (dev machine conflict). Makefile curl commands assume default port 8000.

## Architecture

### Startup / Runtime

FastAPI lifespan (`sentinel/api/main.py`):
1. Waits for SQL Server readiness (30 retries × 2s)
2. Starts background **monitor loop** — polls DMVs every 10s via `sp_capture_health_snapshot`, creates incidents for threshold violations, auto-remediates open incidents, escalates stale incidents
3. Starts async **job runner** — cron-scheduled SQL jobs (ETL, cleanup, validation)

### Dependency Injection

`sentinel/api/dependencies.py` has a singleton `AppState` holding all engine instances. Routes inject via `Depends(get_state)`. Constructor wires: `ConnectionManager` → `HealthCollector`, `BlockerDetector`, `IncidentManager`, `ValidationEngine`, `JobRunner`, `ChaosEngine`, `RemediationEngine`, `DataCatalogEngine`.

### Package Responsibilities

| Package | What it does |
|---------|-------------|
| `sentinel/monitor/` | `HealthCollector` reads DMVs + evaluates thresholds. `BlockerDetector` uses recursive CTE on `sys.dm_exec_requests`. `IncidentManager` manages lifecycle state machine: DETECTED → INVESTIGATING → REMEDIATING → RESOLVED \| ESCALATED. Dedup via `dedup_key`. Auto-postmortem on resolution. `HealthcareMonitor` tracks pharmacy claims, rejection rates, generic dispensing, and patient adherence (PDC). |
| `sentinel/chaos/` | 9 scenarios (6 infrastructure + 3 healthcare: claim volume spike, PHI exposure, formulary change). Cooldown management. Auto-creates incidents. Scenarios defined in `BUILTIN_SCENARIOS` dict in `scenarios.py`. |
| `sentinel/remediation/` | Pattern-matches incident types → actions (kill_session, cleanup_stale, restart_job, quarantine_data). Escalates on failure. |
| `sentinel/validation/` | 6 rule types: null_check, range_check, referential, duplicate, freshness, custom_sql. Factory pattern in `rules.py`. 24 rules (10 operational + 14 healthcare). |
| `sentinel/governance/` | `DataCatalogEngine` — schema scanning, PHI/PII auto-classification via regex, catalog CRUD, ETL lineage recording, PHI masked export (`mask_patients_for_export`), PHI access audit logging. |
| `sentinel/jobs/` | Async cron scheduler. Parses `*/5 * * * *` and `@every 30s` syntax. Logs runs to `job_runs` table. |
| `sentinel/config/` | Pydantic models (`models.py`) + YAML loader (`loader.py`) with `${ENV_VAR:default}` substitution. |
| `sentinel/db/` | `ConnectionManager` — pyodbc wrapper with context managers. SQL file loader with `@lru_cache`. |
| `sentinel/web/` | Dark theme dashboard. JS auto-refreshes from `/api/dashboard` every 5s. |

### Configuration

All behavior is YAML-driven in `config/`:
- `sentinel.yaml` — DB connection, warning/critical thresholds, monitor settings (poll interval, auto_remediate, escalation timeout)
- `jobs.yaml` — 13 scheduled jobs with cron expressions (7 operational + 6 healthcare ETL)
- `validation_rules.yaml` — 24 data quality rules (10 operational + 14 healthcare)
- `chaos_scenarios.yaml` — 9 chaos scenarios with severities/cooldowns (6 infrastructure + 3 healthcare)

### Database Schema

SQL init scripts in `sql/init/` run alphabetically by `init-db` container (prefixed `01_` through `13_`).

Core monitoring tables: `health_snapshots`, `incidents`, `job_runs`, `validation_results`, `remediation_log`, `postmortems`.
Sample app tables: `customers`, `orders`, `order_items` (for validation testing).
ETL tables: `daily_order_summary`, `customer_health`, `incident_metrics`.
Healthcare OLTP: `providers`, `patients`, `medications`, `pharmacies`, `prescriptions`, `pharmacy_claims` (partitioned), `drug_interactions`, `prior_authorizations`.
Healthcare star schema: `fact_pharmacy_claims` (columnstore), `dim_patient` (SCD2), `dim_medication`, `dim_pharmacy`, `dim_provider`, `dim_date`, `patient_adherence`.
Governance: `data_catalog`, `data_lineage`, `phi_access_log`.
Healthcare ETL: `stg_pharmacy_claims`, `pharmacy_fill_summary`.

DMV queries in `sql/dmv/` loaded at runtime.

## Testing

### Mock Database

`tests/conftest.py` provides `MockConnectionManager` — stores data in `_tables` dict, pattern-matches SQL strings to route queries. When adding tests with new SQL patterns, check if the mock handles them; add a handler if not.

Fixtures: `mock_db` (fresh MockConnectionManager) and `config` (SentinelConfig with test thresholds + sample validation rules).

### Integration Tests

`tests/integration/test_health_api.py` uses FastAPI TestClient. **Critical pattern:** must override lifespan with `_noop_lifespan` to prevent the real lifespan from trying to connect to SQL Server (30 retries × 2s = 60s hang). Also uses `dependency_overrides[get_state]` to inject mock state. MockAppState must include `catalog` attribute (DataCatalogEngine).

### Stress Tests

`tests/stress/test_load.py` — 13 tests for dedup storms (500 alerts), throughput benchmarks (1000+ incidents/sec), escalation sweeps, chaos cooldown enforcement.

## Gotchas

- **`SET QUOTED_IDENTIFIER ON`** required at top of all SQL init scripts (needed for filtered indexes and XML ring buffer operations)
- **`ValidationEngine.__init__`** takes `(db, rules: list[ValidationRuleConfig])`, not `(db, config)` — config is unwrapped before passing
- **`sp_etl_customer_health`** uses `GREATEST`/`LEAST` — SQL Server 2022+ only
- **`python3` vs `python`** — dev machine uses `python3`; Docker container has `python`. Makefile uses bare `pytest` (assumes venv)
- **Parameterized SQL** throughout — all queries use `?` placeholders, no string interpolation
- **`pharmacy_claims`** is partitioned — PK includes `service_date` as the partition column

## Style

- Line length: 100 (black + isort + flake8)
- isort profile: `black`
- Conventional commits (template in `.gitmessage`): `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`
