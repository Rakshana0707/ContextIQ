# ContextIQ Operations & Incident Response Runbook
## SRE Guide, Monitoring Alerts, and Emergency Procedures

**Applies To**: ContextIQ Backend API, Workflow Execution Engine, Event Ingestion Pipeline  
**Audience**: Site Reliability Engineers, DevOps, on-call developers  

---

## 1. Routine Health & Diagnostic Checks

### Health Endpoints
- **Liveness**: `GET /api/v1/health/live`
  - Returns `200 OK` if the process is alive. Used by Kubernetes/Docker liveness probes.
- **Readiness**: `GET /api/v1/health/ready`
  - Validates active database connection pool and internal queue availability.
- **Metrics**: `GET /api/v1/metrics`
  - Exposes standard Prometheus text metrics: `contextiq_http_requests_total`, `contextiq_http_request_duration_seconds`, `contextiq_workflow_execution_duration_ms`, `contextiq_events_processed_total`.

---

## 2. Common Alerts & Triage Runbooks

### Alert 1: Elevated Event Processing Dead-Letter Count
- **Symptom**: `contextiq_events_deadletter_total` rate > 5 per minute.
- **Triage**:
  1. Inspect dead-letter records:
     ```sql
     SELECT id, error_code, error_reason, created_at 
     FROM dead_letter_event_records 
     ORDER BY created_at DESC LIMIT 10;
     ```
  2. If `error_code == 'CONSENT_REQUIRED'`, user has revoked telemetry consent; client agent is out of sync. Advise user to sync consent settings.
  3. If `error_code == 'VALIDATION_FAILED'`, an external integration or mobile client emitted an incompatible schema version. Inspect `raw_payload`.

### Alert 2: Circuit Breaker Open on Calendar Integration
- **Symptom**: Logs contain `CircuitBreakerError: Circuit calendar_sync is OPEN`.
- **Triage**:
  1. Check external provider status (Google Workspace / Microsoft 365 status pages).
  2. The circuit automatically enters `HALF-OPEN` after 60 seconds of cooldown.
  3. To manually force-reset a stuck circuit:
     ```python
     from app.services.observability import circuit_breaker
     circuit_breaker.reset("calendar_sync")
     ```

### Alert 3: In-Flight Workflow Plan Stuck in 'EXECUTING'
- **Symptom**: Plan has been in `EXECUTING` state for > 15 minutes.
- **Remediation**:
  1. Locate the stuck plan:
     ```sql
     SELECT id, user_id, title, status, started_at 
     FROM workflow_execution_plans 
     WHERE status = 'EXECUTING' AND started_at < NOW() - INTERVAL '15 minutes';
     ```
  2. Mark as `FAILED` or trigger compensation:
     ```python
     from app.services.workflow_planner import WorkflowPlanner
     WorkflowPlanner.transition_plan_status(db, plan_id, user_id, WorkflowLifecycleState.FAILED)
     ```

---

## 3. Global Emergency Kill Switch (Administrator)

If an automated workflow behaves erratically or third-party APIs exhibit cascading failures:

### Engaging Global Emergency Stop
Run via administrative shell or API:
```bash
POST /api/v1/admin/emergency-stop
Authorization: Bearer <ADMIN_JWT>
{
  "reason": "Cascading failures on Microsoft Calendar API",
  "scope": "ADMIN_GLOBAL"
}
```
**Outcome**: All automated executions across all users are immediately halted and blocked.

### Resuming Normal Operation
```bash
POST /api/v1/admin/emergency-stop/lift
Authorization: Bearer <ADMIN_JWT>
{
  "reason": "Microsoft API restored; regression tests verified"
}
```

---

## 4. Database Backup and Disaster Recovery

### Automated Backup Procedure
```bash
# Nightly compressed backup with SHA-256 integrity checksum
pg_dump -h localhost -U contextiq_user contextiq_prod | gzip > /backups/contextiq_$(date +%Y%m%d_%H%M%S).sql.gz
sha256sum /backups/contextiq_*.sql.gz > /backups/checksums.txt
```

### Point-in-Time Restore Procedure
```bash
# 1. Stop app traffic
docker compose stop backend

# 2. Restore database
gunzip -c /backups/contextiq_YYYYMMDD_HHMMSS.sql.gz | psql -h localhost -U contextiq_user -d contextiq_prod

# 3. Restart application
docker compose start backend
```
