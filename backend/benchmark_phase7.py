"""
Performance Benchmark Harness for ContextIQ Phase 7.10.
Measures genuine wall-clock latencies across:
1. Event Ingestion & Deduplication
2. Multi-Step Workflow Planning & Scoring
3. Governed DAG Action Execution
4. Policy Evaluation & Consent Checking
5. Audit Trail Append & Retrieval
"""
from __future__ import annotations

import statistics
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.enums import TaskPriority, TaskStatus
from app.models.notification_models import UserNotificationPreference
from app.models.task import Task
from app.models.telemetry_consent import TelemetryConsent
from app.models.user import User
from app.models.workflow_models import WorkflowExecutionPlan
from app.schemas.event_schemas import EventSource, StandardEvent, StandardEventType
from app.schemas.policy_schemas import PermissionScope
from app.schemas.workflow_schemas import (
    DependencyType,
    WorkflowDependencySchema,
    WorkflowLifecycleState,
    WorkflowStepSchema,
)
from app.services.action_handlers import ActionHandlers
from app.services.event_processor import EventProcessor
from app.services.policy_engine import PolicyEngine
from app.services.safety_engine import AuditLogger
from app.services.workflow_execution_engine import WorkflowExecutionEngine
from app.services.workflow_planner import WorkflowPlanner


def run_benchmark():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Setup User & Policy
    u = User(
        id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
        email="bench@contextiq.io",
        display_name="Benchmark User",
        is_active=True,
    )
    db.add(u)
    consent = TelemetryConsent(
        user_id=u.id,
        consent_status="GRANTED",
        enabled_categories=["APP_TRANSITIONS", "SESSION_RECONSTRUCTION"],
        granted_timestamp=datetime.now(timezone.utc),
    )
    db.add(consent)
    pref = UserNotificationPreference(
        user_id=u.id,
        quiet_hours_enabled=False,
        max_notifications_per_day=1000,
        is_paused=False,
    )
    db.add(pref)
    db.commit()

    for scope in [
        PermissionScope.TASKS_READ,
        PermissionScope.TASKS_WRITE,
        PermissionScope.CALENDAR_READ,
        PermissionScope.CALENDAR_EVENTS_CREATE,
        PermissionScope.CALENDAR_EVENTS_MODIFY,
        PermissionScope.NOTIFICATIONS_SEND,
        PermissionScope.AUTOMATION_SCHEDULE_RUN,
        PermissionScope.WORKFLOWS_EXECUTE,
    ]:
        PolicyEngine.grant_scope(db, u.id, scope)

    # Pre-populate tasks for execution
    tasks = []
    for i in range(50):
        t = Task(
            id=uuid.uuid4(),
            user_id=u.id,
            title=f"Benchmark Task {i}",
            status=TaskStatus.PENDING,
            priority=TaskPriority.LOW,
        )
        db.add(t)
        tasks.append(t)
    db.commit()

    N = 30
    latencies = {
        "event_ingestion": [],
        "policy_evaluation": [],
        "workflow_planning": [],
        "workflow_execution": [],
        "audit_append": [],
    }

    # 1. Event Ingestion Latency
    for i in range(N):
        now = datetime.now(timezone.utc)
        ev = StandardEvent(
            event_id=f"bench-evt-{uuid.uuid4()}",
            event_type=StandardEventType.CONTEXT_SWITCH.value,
            user_id=u.id,
            event_timestamp=now,
            ingestion_timestamp=now,
            source=EventSource.DESKTOP_TELEMETRY.value,
            payload={"app": "BenchmarkRunner", "switch_index": i},
            idempotency_key=f"bench_key_{uuid.uuid4()}",
        )
        t0 = time.perf_counter()
        EventProcessor.process_event(db=db, event_or_req=ev)
        t1 = time.perf_counter()
        latencies["event_ingestion"].append((t1 - t0) * 1000.0)

    # 2. Policy Evaluation Latency
    for i in range(N):
        t0 = time.perf_counter()
        PolicyEngine.evaluate_action_policy(
            db=db,
            user_id=u.id,
            action_identifier="task:update_priority",
            parameters={"task_id": str(tasks[i].id), "new_priority": "HIGH"},
        )
        t1 = time.perf_counter()
        latencies["policy_evaluation"].append((t1 - t0) * 1000.0)

    # 3. Multi-Step Workflow Planning & Scoring Latency
    for i in range(N):
        t0 = time.perf_counter()
        plan = WorkflowPlanner.plan_behavioral_workflow(
            db=db,
            user_id=u.id,
            trigger_type="FORGETTING_RISK_SPIKE",
            behavioral_context={"task_title": tasks[i].title, "lapse_probability": 0.85},
            task_id=tasks[i].id,
        )
        t1 = time.perf_counter()
        latencies["workflow_planning"].append((t1 - t0) * 1000.0)

    # 4. Governed DAG Action Execution Latency
    for i in range(N):
        # Create approved 2-step plan
        steps = [
            WorkflowStepSchema(
                step_key="s1",
                name="Update Priority",
                action_identifier="task:update_priority",
                parameters={"task_id": str(tasks[i].id), "new_priority": "CRITICAL"},
                is_optional=False,
                order_index=1,
            ),
            WorkflowStepSchema(
                step_key="s2",
                name="Buffer",
                action_identifier="recovery:insert_post_interruption_buffer",
                parameters={"buffer_duration_minutes": 10},
                is_optional=True,
                order_index=2,
            ),
        ]
        plan = WorkflowExecutionPlan(
            user_id=u.id,
            title=f"Exec Bench Plan {i}",
            status=WorkflowLifecycleState.APPROVED.value,
            version=1,
            idempotency_key=f"bench_exec_{uuid.uuid4().hex}",
            plan_steps=[s.model_dump(mode="json") for s in steps],
            plan_dependencies=[],
            rationale="Benchmarking execution engine",
            expected_benefits={},
            potential_side_effects={},
            utility_score=0.9,
            reversibility_summary={"is_fully_reversible": True},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        t0 = time.perf_counter()
        WorkflowExecutionEngine.execute_plan(db, plan.id, u.id)
        t1 = time.perf_counter()
        latencies["workflow_execution"].append((t1 - t0) * 1000.0)

    # 5. Audit Logging Append Latency
    for i in range(N):
        t0 = time.perf_counter()
        AuditLogger.record_event(
            db=db,
            user_id=u.id,
            event_type="STEP_COMPLETED",
            action_identifier="task:update_priority",
            result_status="COMPLETED",
            payload={"task_id": str(tasks[i].id), "iteration": i},
        )
        t1 = time.perf_counter()
        latencies["audit_append"].append((t1 - t0) * 1000.0)

    print("\n--- CONTEXTIQ PHASE 7 EMPIRICAL PERFORMANCE BENCHMARK ---")
    for category, vals in latencies.items():
        vals.sort()
        mean = statistics.mean(vals)
        median = statistics.median(vals)
        p95 = vals[int(len(vals) * 0.95)]
        p99 = vals[int(len(vals) * 0.99)]
        print(f"{category:25s} | Mean: {mean:6.2f}ms | Median(p50): {median:6.2f}ms | p95: {p95:6.2f}ms | p99: {p99:6.2f}ms | Min: {vals[0]:6.2f}ms | Max: {vals[-1]:6.2f}ms")


if __name__ == "__main__":
    run_benchmark()
