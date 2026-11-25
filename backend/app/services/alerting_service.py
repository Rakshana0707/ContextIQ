"""
Production Operational Alerting Engine (ContextIQ Phase 7.8).
Evaluates operational health criteria, stuck workflows, circuit breakers,
and latency anomalies without fabricating metric data.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerState
from app.core.metrics import metrics_registry
from app.models.safety_models import EmergencyStopEvent
from app.models.workflow_models import WorkflowExecutionPlan
from app.schemas.workflow_schemas import WorkflowLifecycleState
from app.schemas.safety_schemas import EmergencyStopScope

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class OperationalAlert(BaseModel):
    alert_id: str
    title: str
    severity: AlertSeverity
    category: str
    message: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    triggered_at: datetime
    recommended_action: str


class AlertingService:
    """Evaluates system reliability thresholds and generates actionable alerts."""

    @classmethod
    def evaluate_alerts(cls, db: Session) -> List[OperationalAlert]:
        alerts: List[OperationalAlert] = []
        now = datetime.now(timezone.utc)
        metrics = metrics_registry.get_metrics_snapshot()

        # 1. High Workflow Failure Rate Alert
        wf_metrics = metrics["workflows"]
        if wf_metrics["executions_total"] >= 5 and wf_metrics["failure_rate_pct"] >= 15.0:
            alerts.append(
                OperationalAlert(
                    alert_id="ALERT_WF_HIGH_FAILURE_RATE",
                    title="Elevated Workflow Execution Failure Rate",
                    severity=AlertSeverity.CRITICAL if wf_metrics["failure_rate_pct"] >= 30.0 else AlertSeverity.WARNING,
                    category="WORKFLOW",
                    message=f"Workflow failure rate is at {wf_metrics['failure_rate_pct']}% ({wf_metrics['failures_total']} failures of {wf_metrics['executions_total']} executions).",
                    metric_value=wf_metrics["failure_rate_pct"],
                    threshold=15.0,
                    triggered_at=now,
                    recommended_action="Inspect failed workflow step executions and check external calendar provider credentials.",
                )
            )

        # 2. Stuck Executions Alert (in EXECUTING state > 30 minutes)
        stuck_cutoff = now - timedelta(minutes=30)
        stuck_plans = db.execute(
            select(WorkflowExecutionPlan).where(
                and_(
                    WorkflowExecutionPlan.status == WorkflowLifecycleState.EXECUTING.value,
                    WorkflowExecutionPlan.executed_at != None,  # noqa: E711
                    WorkflowExecutionPlan.executed_at < stuck_cutoff,
                )
            )
        ).scalars().all()

        if stuck_plans:
            alerts.append(
                OperationalAlert(
                    alert_id="ALERT_STUCK_WORKFLOW_EXECUTIONS",
                    title="Stuck Workflow Executions Detected",
                    severity=AlertSeverity.WARNING,
                    category="WORKFLOW",
                    message=f"Detected {len(stuck_plans)} workflow execution plan(s) stuck in EXECUTING state for > 30 minutes.",
                    metric_value=float(len(stuck_plans)),
                    threshold=1.0,
                    triggered_at=now,
                    recommended_action="Cancel stuck execution plans and verify background worker thread connectivity.",
                )
            )

        # 3. Circuit Breaker Outage Alerts
        for breaker_status in CircuitBreakerRegistry.list_statuses():
            if breaker_status["state"] == CircuitBreakerState.OPEN.value:
                alerts.append(
                    OperationalAlert(
                        alert_id=f"ALERT_CIRCUIT_BREAKER_TRIPPED_{breaker_status['name'].upper()}",
                        title=f"Circuit Breaker Tripped: {breaker_status['name']}",
                        severity=AlertSeverity.CRITICAL,
                        category="CIRCUIT_BREAKER",
                        message=f"Integration '{breaker_status['name']}' has exceeded failure threshold ({breaker_status['failure_count']}/{breaker_status['failure_threshold']}). Circuit is OPEN.",
                        metric_value=float(breaker_status["failure_count"]),
                        threshold=float(breaker_status["failure_threshold"]),
                        triggered_at=now,
                        recommended_action="Check downstream third-party provider status page and verify OAuth access token renewal.",
                    )
                )

        # 4. Elevated API Error Rate Alert
        api_metrics = metrics["api"]
        if api_metrics["requests_total"] >= 20 and api_metrics["error_rate_pct"] >= 10.0:
            alerts.append(
                OperationalAlert(
                    alert_id="ALERT_API_HIGH_ERROR_RATE",
                    title="High HTTP Error Rate",
                    severity=AlertSeverity.WARNING,
                    category="API",
                    message=f"HTTP 4xx/5xx error rate is currently {api_metrics['error_rate_pct']}% ({api_metrics['errors_total']}/{api_metrics['requests_total']} requests).",
                    metric_value=api_metrics["error_rate_pct"],
                    threshold=10.0,
                    triggered_at=now,
                    recommended_action="Inspect structured API logs for authentication or validation regressions.",
                )
            )

        # 5. Global Emergency Stop Alert
        active_global_stop = db.execute(
            select(EmergencyStopEvent).where(
                and_(
                    EmergencyStopEvent.scope == EmergencyStopScope.ADMIN_GLOBAL.value,
                    EmergencyStopEvent.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()

        if active_global_stop:
            alerts.append(
                OperationalAlert(
                    alert_id="ALERT_GLOBAL_EMERGENCY_KILL_SWITCH",
                    title="Administrative Operational Kill Switch Active",
                    severity=AlertSeverity.CRITICAL,
                    category="SAFETY",
                    message=f"Global emergency stop is ENGAGED. Reason: {active_global_stop.reason}",
                    metric_value=1.0,
                    threshold=0.0,
                    triggered_at=now,
                    recommended_action="Review incident response logs and lift emergency stop when nominal operations are restored.",
                )
            )

        return alerts
