# Phase 6 Production Deployment and Operations Guide

## 1. Overview and Pre-Deployment Checklist

This guide provides operational procedures for deploying ContextIQ Phase 6 (Advanced Predictive Intelligence, Causal Modeling, and Decision Support) into production environments.

### 1.1 Pre-Flight Verification Checklist
Prior to promoting any build to staging or production, verify that:
- [x] All backend unit and integration tests pass: `python -m pytest backend/tests/ -v`.
- [x] Dedicated Phase 6 test suite passes: `python -m pytest backend/tests/test_phase6_integration_and_release.py -v`.
- [x] Full platform regression suite passes with 0 regressions.
- [x] Frontend type check completes cleanly: `cd frontend && npx tsc --noEmit`.
- [x] Frontend test suite passes: `cd frontend && npm test`.
- [x] System verification script succeeds: `powershell -ExecutionPolicy Bypass -File .\verify_system.ps1`.
- [x] Model artifacts and calibrators are validated and registered in the Model Registry.
- [x] Database migration scripts execute idempotently.

---

## 2. Environment Configuration

Phase 6 introduces specific configuration flags in `backend/app/core/config.py` and environment files (`.env`):

```bash
# ==============================================================================
# ContextIQ Phase 6 Predictive Intelligence Configuration
# ==============================================================================

# Model Registry Storage Path
CONTEXTIQ_MODEL_REGISTRY_DIR="/var/lib/contextiq/models"

# Causal & Counterfactual Settings
CONTEXTIQ_CAUSAL_MIN_SAMPLE_SIZE=30
CONTEXTIQ_PROPENSITY_TRIM_MIN=0.05
CONTEXTIQ_PROPENSITY_TRIM_MAX=0.95
CONTEXTIQ_ENABLE_CAUSAL_INFERENCE=true

# Uncertainty & Conformal Prediction Settings
CONTEXTIQ_CONFORMAL_ALPHA=0.10             # 90% Nominal Coverage
CONTEXTIQ_CALIBRATION_METHOD="isotonic"     # "isotonic" or "platt"
CONTEXTIQ_ABSTENTION_THRESHOLD=0.60         # Min calibrated prob to recommend
CONTEXTIQ_OOD_DISTANCE_THRESHOLD=3.5        # Mahalanobis distance OOD cutoff

# Multi-Objective Optimization Bounds
CONTEXTIQ_MAX_DAILY_NOTIFICATIONS=6
CONTEXTIQ_QUIET_HOURS_START="22:00"
CONTEXTIQ_QUIET_HOURS_END="08:00"

# Behavioral Digital Twin Simulation
CONTEXTIQ_ALLOW_WHAT_IF_SIMULATION=true
CONTEXTIQ_MAX_SIMULATION_HORIZON_DAYS=7
CONTEXTIQ_REQUIRE_EXPLICIT_APPROVAL=true    # Zero unapproved workflow execution
```

---

## 3. Database Migration and Schema Management

Phase 6 models build on existing SQLAlchemy declarative schemas and maintain 100% backward compatibility with Phase 1–5 tables.

### 3.1 Migration Steps
1. **Backup Database:**
   ```bash
   # PostgreSQL
   pg_dump -U contextiq -d contextiq_prod -F c -b -v -f /backups/contextiq_pre_phase6.dump
   
   # SQLite (Development / Single-Node)
   sqlite3 contextiq.db ".backup '/backups/contextiq_pre_phase6.sqlite'"
   ```

2. **Execute Alembic Migrations:**
   ```bash
   cd backend
   alembic upgrade head
   ```

3. **Verify Schema Tables:**
   Ensure the following Phase 6 tables exist:
   - `workflow_execution_proposals`
   - `workflow_proposal_steps`
   - `conformal_calibration_sets`
   - `causal_analysis_snapshots`
   - `recovery_prediction_logs`

---

## 4. Model Registry and Serialization

ContextIQ manages predictive models using an on-disk, versioned Model Registry:
- **Location:** Stored under `CONTEXTIQ_MODEL_REGISTRY_DIR/phase6/`.
- **Format:** Serialized pipeline objects (`joblib` or `pickle`) alongside cryptographic SHA256 checksums and Pydantic metadata files.
- **Model Manifest:** Each registered model contains a `model_manifest.json` describing:
  - `model_id` (UUID)
  - `model_type` (`AFT_LOGNORMAL`, `COX_STRATIFIED`, `GBDT_SEQUENCE`, `SPLIT_CONFORMAL`)
  - `feature_schema_version`
  - `trained_at_timestamp`
  - `holdout_c_index` or `holdout_mae`
  - `calibration_ece`

### 4.1 Deployment Command
```bash
python -m backend.app.services.model_registry register \
  --model-type AFT_LOGNORMAL \
  --artifact-path /tmp/recovery_lognormal_v1.joblib \
  --metrics '{"mae": 4.12, "rmse": 6.85}'
```

---

## 5. API Surface and Public Endpoints

Ensure reverse proxies (Nginx, Traefik, AWS ALB) allow traffic to all Phase 6 routes under `/api/v1/`:
- `GET /api/v1/analytics/recovery/benchmark`: Cognitive recovery benchmark and pipeline status.
- `POST /api/v1/analytics/recovery/predict`: Single-episode recovery duration prediction.
- `GET /api/v1/causal/questions`: Registered causal inquiry questions and DAG definitions.
- `POST /api/v1/causal/estimate`: Compute causal ATE with G-Computation and IPW.
- `POST /api/v1/counterfactual/candidates`: Multi-intervention candidate counterfactual rankings.
- `GET /api/v1/sequence/benchmark`: Temporal sequence model evaluation against GBDT baseline.
- `GET /api/v1/survival/benchmark`: Competing risk survival model metrics.
- `GET /api/v1/uncertainty/audit`: Conformal prediction intervals and calibration audits.
- `POST /api/v1/analytics/optimization/interventions`: Multi-objective Pareto frontier solver.
- `POST /api/v1/analytics/simulation/scenarios`: Digital Twin What-If scenario generator.
- `POST /api/v1/analytics/simulation/orchestrate`: Generate user-approved workflow proposals.
- `POST /api/v1/analytics/simulation/orchestrate/{proposal_id}/approve`: Explicit human approval gate.
- `POST /api/v1/analytics/simulation/orchestrate/{proposal_id}/rollback`: Two-phase workflow rollback.

---

## 6. Rollback Runbook and Emergency Procedures

If a critical failure, latency regression, or prediction drift is detected post-deployment, follow this runbook:

### 6.1 Fast Circuit-Breaker Degradation (No Restart Required)
If predictive intelligence or causal models experience latency spikes, enable fallback mode via environment variable:
```bash
# Sets system to fall back to Phase 5 heuristics
export CONTEXTIQ_ENABLE_CAUSAL_INFERENCE=false
export CONTEXTIQ_ENABLE_ABSTENTION_FALLBACK=true
kill -HUP $(pgrep -f "uvicorn.*contextiq")
```

### 6.2 Full Application Rollback
To revert to the Phase 5 release:
1. **Revert Git Release:**
   ```bash
   git checkout tags/v5.0.0
   ```
2. **Revert Database Migrations:**
   ```bash
   cd backend
   alembic downgrade -1
   ```
3. **Restart Application Services:**
   ```bash
   docker-compose restart backend frontend
   ```
4. **Verify Health:**
   ```bash
   curl -f http://localhost:8000/api/v1/health
   ```

---

## 7. Health Monitoring and Telemetry Validation

- **Health Endpoint:** `GET /api/v1/health` checks DB connectivity, model registry availability, and cache status.
- **Latency Alarms:** Set alerts if `POST /api/v1/analytics/recovery/predict` p95 exceeds $250\text{ ms}$.
- **Abstention Rate Alarms:** Alert if the abstention rate exceeds $35\%$ over a rolling 1-hour window (indicates significant distribution shift or data collection failure).
- **Zero Silent Mutation Auditing:** The database is continuously monitored to ensure no `WorkflowExecutionProposal` is executed where `is_approved == False`. Any violation triggers an immediate critical security alert.
