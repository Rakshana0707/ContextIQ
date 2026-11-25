"""
FastAPI router for Production Observability, Monitoring, and Metrics (ContextIQ Phase 7.8).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.circuit_breaker import CircuitBreakerRegistry
from app.core.metrics import metrics_registry
from app.db.session import get_db
from app.services.alerting_service import AlertingService, OperationalAlert

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/metrics")
def get_metrics_snapshot() -> Dict[str, Any]:
    """Returns live operational metrics across API, database, workflows, and ML inference."""
    return metrics_registry.get_metrics_snapshot()


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
def get_prometheus_metrics() -> str:
    """Exports operational metrics in standard Prometheus text format."""
    return metrics_registry.export_prometheus_format()


@router.get("/alerts", response_model=List[OperationalAlert])
def get_operational_alerts(db: Session = Depends(get_db)) -> List[OperationalAlert]:
    """Evaluates system reliability thresholds and returns active operational alerts."""
    return AlertingService.evaluate_alerts(db)


@router.get("/circuit-breakers")
def get_circuit_breakers() -> List[Dict[str, Any]]:
    """Returns real-time status of all integration circuit breakers."""
    return CircuitBreakerRegistry.list_statuses()


@router.post("/circuit-breakers/{name}/reset")
def reset_circuit_breaker(name: str) -> Dict[str, Any]:
    """Resets a circuit breaker to CLOSED state."""
    breaker = CircuitBreakerRegistry.get_or_create(name)
    breaker.reset()
    return {"status": "SUCCESS", "circuit_breaker": breaker.get_status()}


@router.post("/circuit-breakers/{name}/trip")
def trip_circuit_breaker(name: str) -> Dict[str, Any]:
    """Manually trips a circuit breaker to OPEN state for operational drills or isolation."""
    breaker = CircuitBreakerRegistry.get_or_create(name)
    breaker.trip()
    return {"status": "SUCCESS", "circuit_breaker": breaker.get_status()}


@router.get("/system-status")
def get_system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Administrative overview combining metrics, circuit breakers, and active alerts
    without exposing individual user data.
    """
    metrics = metrics_registry.get_metrics_snapshot()
    alerts = AlertingService.evaluate_alerts(db)
    breakers = CircuitBreakerRegistry.list_statuses()

    any_critical_alert = any(a.severity.value == "CRITICAL" for a in alerts)
    overall_health = "DEGRADED" if alerts else "HEALTHY"
    if any_critical_alert:
        overall_health = "CRITICAL"

    return {
        "overall_health": overall_health,
        "active_alerts_count": len(alerts),
        "alerts": [a.model_dump() for a in alerts],
        "metrics": metrics,
        "circuit_breakers": breakers,
    }
