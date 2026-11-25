"""
Health, Liveness, and Readiness Probes (ContextIQ Phase 7.8).
Provides clean operational health checks without leaking internal infrastructure secrets.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerState
from app.core.config import get_settings
from app.core.metrics import metrics_registry
from app.db.session import get_db
from app.services.safety_engine import EmergencyStopEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/live")
@router.get("/live")
def liveness() -> Dict[str, str]:
    """Lightweight liveness probe: returns 200 OK if server process is running."""
    return {"status": "UP"}


@router.get("/health/ready")
@router.get("/ready")
def readiness(response: Response, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Readiness probe: validates database connectivity, circuit breaker health,
    and emergency stop state before routing traffic.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    subsystems: Dict[str, str] = {}
    is_ready = True

    # 1. Database Connectivity Probe
    db_start = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        db_duration_ms = round((time.perf_counter() - db_start) * 1000, 2)
        metrics_registry.record_db_query(db_duration_ms)
        subsystems["database"] = "UP"
    except Exception as e:
        logger.error(f"Readiness probe failed database check: {e}")
        subsystems["database"] = "DOWN"
        metrics_registry.record_db_query(0.0, error=True)
        is_ready = False

    # 2. Integration Circuit Breakers Check
    breakers = CircuitBreakerRegistry.list_statuses()
    any_breaker_open = any(b["state"] == CircuitBreakerState.OPEN.value for b in breakers)
    subsystems["circuit_breakers"] = "DEGRADED" if any_breaker_open else "UP"

    # 3. Emergency Stop State
    if is_ready:
        try:
            is_stopped, _ = EmergencyStopEngine.is_emergency_stop_active(db)
            subsystems["emergency_stop"] = "ACTIVE" if is_stopped else "CLEAR"
        except Exception as e:
            logger.warning(f"Could not check emergency stop state: {e}")
            subsystems["emergency_stop"] = "UNKNOWN"
    else:
        subsystems["emergency_stop"] = "UNKNOWN"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    overall_status = "READY" if (is_ready and not any_breaker_open) else ("DEGRADED" if is_ready else "NOT_READY")

    return {
        "status": overall_status,
        "app": settings.APP_NAME,
        "timestamp": now.isoformat(),
        "subsystems": subsystems,
    }


@router.get("/health")
def health_check(response: Response, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Backward-compatible health check."""
    return readiness(response=response, db=db)


@router.get("/health/detailed")
def detailed_health(response: Response, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive internal operational diagnostic including latency summaries,
    circuit breaker states, and uptime.
    """
    ready_data = readiness(response=response, db=db)
    metrics_data = metrics_registry.get_metrics_snapshot()
    breakers_data = CircuitBreakerRegistry.list_statuses()

    return {
        **ready_data,
        "metrics_summary": metrics_data,
        "circuit_breakers": breakers_data,
    }
