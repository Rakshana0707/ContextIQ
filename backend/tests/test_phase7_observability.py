"""
Comprehensive Test Suite for Phase 7.8: Production Observability, Monitoring, and Reliability Engineering.
Validates:
1. Structured JSON logging with strict secret and token redaction.
2. Distributed tracing correlation headers (X-Request-ID, X-Correlation-ID, X-Response-Time-Ms).
3. Live metrics registry tracking latencies, percentiles, error rates, and Prometheus text export.
4. Fault-isolating Circuit Breakers (CLOSED -> OPEN -> HALF_OPEN -> CLOSED, fail-fast behavior).
5. Operational Health Probes (/health/live, /health/ready, /health/detailed, 503 on DB disconnect).
6. Deterministic Alerting Engine for failure rates, stuck executions, tripped breakers, and kill switch.
7. Observability API endpoints and circuit breaker manual controls.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitBreakerState,
)
from app.core.logging_config import (
    StructuredJsonFormatter,
    correlation_id_ctx,
    request_id_ctx,
    scrub_sensitive_text,
    user_id_ctx,
)
from app.core.metrics import MetricsRegistry
from app.db.session import Base, get_db
from app.main import app
from app.models.automation_rule import AutomationRule
from app.models.safety_models import (
    EmergencyStopEvent,
    WorkflowAuditEvent,
    WorkflowRollbackRecord,
)
from app.models.task import Task
from app.models.user import User
from app.models.workflow_models import (
    WorkflowDefinition,
    WorkflowExecutionPlan,
    WorkflowPlanVersion,
    WorkflowStepExecution,
)
from app.schemas.safety_schemas import EmergencyStopScope
from app.services.alerting_service import AlertingService, AlertSeverity


TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


class TestStructuredLogging:
    def test_secret_and_token_redaction(self):
        formatter = StructuredJsonFormatter(service="contextiq-test")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="User login with token=secret123456 and Bearer eyJhbGciOiJIUzI1NiJ9.test and client_secret=very_secret_key",
            args=(),
            exc_info=None,
        )

        formatted_str = formatter.format(record)
        data = json.loads(formatted_str)

        assert data["service"] == "contextiq-test"
        assert data["severity"] == "INFO"
        assert "secret123456" not in data["message"]
        assert "eyJhbGciOiJIUzI1NiJ9.test" not in data["message"]
        assert "very_secret_key" not in data["message"]
        assert "[REDACTED]" in data["message"]

    def test_context_vars_injection(self):
        formatter = StructuredJsonFormatter(service="contextiq-test")
        req_token = request_id_ctx.set("req-12345")
        corr_token = correlation_id_ctx.set("corr-67890")
        usr_token = user_id_ctx.set("usr-abcdef")

        try:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.WARNING,
                pathname="test.py",
                lineno=25,
                msg="Operational warning occurred",
                args=(),
                exc_info=None,
            )
            data = json.loads(formatter.format(record))
            assert data["request_id"] == "req-12345"
            assert data["correlation_id"] == "corr-67890"
            assert data["user_id"] == "usr-abcdef"
        finally:
            request_id_ctx.reset(req_token)
            correlation_id_ctx.reset(corr_token)
            user_id_ctx.reset(usr_token)


class TestObservabilityMiddleware:
    def test_distributed_tracing_headers(self, client):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert "X-Correlation-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers
        assert float(response.headers["X-Response-Time-Ms"]) >= 0

    def test_custom_correlation_id_preserved(self, client):
        custom_corr_id = "test-custom-correlation-uuid-999"
        response = client.get("/health/live", headers={"X-Correlation-ID": custom_corr_id})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_corr_id


class TestMetricsRegistry:
    def test_metrics_collection_and_percentiles(self):
        registry = MetricsRegistry()
        registry.reset()

        # Record API requests with varied latencies
        registry.record_api_request(10.0, error=False)
        registry.record_api_request(20.0, error=False)
        registry.record_api_request(50.0, error=False)
        registry.record_api_request(100.0, error=True)

        snapshot = registry.get_metrics_snapshot()
        assert snapshot["api"]["requests_total"] == 4
        assert snapshot["api"]["errors_total"] == 1
        assert snapshot["api"]["error_rate_pct"] == 25.0
        assert snapshot["api"]["p95_latency_ms"] >= 10.0

    def test_workflow_metrics(self):
        registry = MetricsRegistry()
        registry.reset()

        registry.record_workflow_execution(250.0, success=True)
        registry.record_workflow_execution(450.0, success=True)
        registry.record_workflow_execution(800.0, success=False)

        snapshot = registry.get_metrics_snapshot()
        assert snapshot["workflows"]["executions_total"] == 3
        assert snapshot["workflows"]["failures_total"] == 1
        assert round(snapshot["workflows"]["failure_rate_pct"], 1) == 33.3

    def test_prometheus_export(self):
        registry = MetricsRegistry()
        registry.reset()
        registry.record_api_request(15.0, error=False)
        registry.record_db_query(5.0)

        prom_text = registry.export_prometheus_format()
        assert "# HELP contextiq_http_requests_total" in prom_text
        assert "# TYPE contextiq_http_requests_total counter" in prom_text
        assert "contextiq_http_requests_total 1" in prom_text


class TestCircuitBreakers:
    def test_circuit_breaker_transitions(self):
        breaker = CircuitBreaker(
            name="test_integration",
            failure_threshold=3,
            recovery_timeout_seconds=0.1,  # 100ms for fast test
            half_open_success_threshold=2,
        )
        assert breaker.state == CircuitBreakerState.CLOSED

        def failing_call():
            raise RuntimeError("Provider connection failed")

        def successful_call():
            return "SUCCESS"

        # 1. Successful execution in CLOSED state
        assert breaker.call(successful_call) == "SUCCESS"
        assert breaker.failure_count == 0

        # 2. Induce failures up to threshold
        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(failing_call)
            assert breaker.state == CircuitBreakerState.CLOSED

        # 3rd failure trips the breaker to OPEN
        with pytest.raises(RuntimeError):
            breaker.call(failing_call)
        assert breaker.state == CircuitBreakerState.OPEN

        # 3. Fail-fast in OPEN state without calling target
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(successful_call)

        # 4. Wait for recovery timeout to transition to HALF_OPEN
        time.sleep(0.12)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # 5. Half-open calls required to restore CLOSED
        assert breaker.call(successful_call) == "SUCCESS"
        assert breaker.state == CircuitBreakerState.HALF_OPEN
        assert breaker.call(successful_call) == "SUCCESS"
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_manual_trip_and_reset(self):
        breaker = CircuitBreakerRegistry.get_or_create("custom_manual_breaker")
        breaker.trip()
        assert breaker.state == CircuitBreakerState.OPEN

        breaker.reset()
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0


class TestHealthProbes:
    def test_liveness_probe(self, client):
        res = client.get("/health/live")
        assert res.status_code == 200
        assert res.json() == {"status": "UP"}

    def test_readiness_probe_healthy(self, client):
        res = client.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("READY", "DEGRADED")
        assert data["subsystems"]["database"] == "UP"

    def test_readiness_probe_database_failure(self, client):
        with patch.object(Session, "execute", side_effect=Exception("Database connection timeout")):
            res = client.get("/health/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "NOT_READY"
            assert data["subsystems"]["database"] == "DOWN"


class TestAlertingService:
    def test_high_workflow_failure_rate_alert(self, db_session):
        registry = MetricsRegistry()
        registry.reset()

        # 3 failures out of 10 executions = 30% failure rate (> 15% threshold)
        for _ in range(7):
            registry.record_workflow_execution(100.0, success=True)
        for _ in range(3):
            registry.record_workflow_execution(100.0, success=False)

        with patch("app.services.alerting_service.metrics_registry", registry):
            alerts = AlertingService.evaluate_alerts(db_session)
            wf_alerts = [a for a in alerts if a.alert_id == "ALERT_WF_HIGH_FAILURE_RATE"]
            assert len(wf_alerts) == 1
            assert wf_alerts[0].severity in (AlertSeverity.CRITICAL, AlertSeverity.WARNING)
            assert wf_alerts[0].threshold == 15.0

    def test_circuit_breaker_open_alert(self, db_session):
        breaker = CircuitBreakerRegistry.get_or_create("google_calendar")
        breaker.trip()

        alerts = AlertingService.evaluate_alerts(db_session)
        cb_alerts = [a for a in alerts if a.category == "CIRCUIT_BREAKER"]
        assert len(cb_alerts) >= 1
        assert any("google_calendar" in a.message.lower() for a in cb_alerts)

        breaker.reset()

    def test_global_kill_switch_alert(self, db_session):
        # Engage global kill switch
        stop = EmergencyStopEvent(
            id=uuid.uuid4(),
            user_id=None,
            scope=EmergencyStopScope.ADMIN_GLOBAL.value,
            reason="Operational drill testing emergency kill switch alert",
            is_active=True,
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(stop)
        db_session.commit()

        alerts = AlertingService.evaluate_alerts(db_session)
        kill_alerts = [a for a in alerts if a.alert_id == "ALERT_GLOBAL_EMERGENCY_KILL_SWITCH"]
        assert len(kill_alerts) == 1
        assert kill_alerts[0].severity == AlertSeverity.CRITICAL


class TestObservabilityAPIEndpoints:
    def test_get_metrics(self, client):
        res = client.get("/api/v1/observability/metrics")
        assert res.status_code == 200
        data = res.json()
        assert "api" in data
        assert "database" in data
        assert "workflows" in data

    def test_get_prometheus_metrics(self, client):
        res = client.get("/api/v1/observability/metrics/prometheus")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        assert "contextiq_uptime_seconds" in res.text

    def test_circuit_breaker_controls(self, client):
        trip_res = client.post("/api/v1/observability/circuit-breakers/google_calendar/trip")
        assert trip_res.status_code == 200
        assert trip_res.json()["circuit_breaker"]["state"] == "OPEN"

        reset_res = client.post("/api/v1/observability/circuit-breakers/google_calendar/reset")
        assert reset_res.status_code == 200
        assert reset_res.json()["circuit_breaker"]["state"] == "CLOSED"

    def test_system_status_endpoint(self, client):
        res = client.get("/api/v1/observability/system-status")
        assert res.status_code == 200
        data = res.json()
        assert "overall_health" in data
        assert "active_alerts_count" in data
        assert "metrics" in data
        assert "circuit_breakers" in data
