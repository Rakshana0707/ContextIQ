"""
Unit & Integration Test Suite for ContextIQ Multi-Objective Intervention Optimization (Phase 6.7).

Validates:
1. 8-dimensional normalized quantitative objectives (higher is strictly better).
2. 7 non-bypassable hard constraints (Quiet hours, Quotas, Calendar, Working hours, Immutability, Consent, Opt-outs).
3. First-class No-Action option and safety fallbacks (negligible lift, excessive uncertainty, high fatigue).
4. Context-dependent dynamic weight adaptation (fatigue vs deadline vs disruption).
5. Pareto dominance determination and frontier rank computation.
6. User preference customization and weight shifting.
7. Safety authorization boundary (proposal-only recommendations).
8. REST API endpoints (/api/v1/optimization/* and /api/v1/analytics/optimization/*).
"""
from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, time, timezone
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


import app.models
from app.db.session import Base
from app.main import app
from app.schemas.counterfactual import CandidateIntervention
from app.schemas.multi_objective_optimization import (
    HardConstraintType,
    MultiObjectiveOptimizationRequest,
    MultiObjectiveOptimizationResponse,
    ObjectiveVector,
    ObjectiveWeights,
    OptimizationObjective,
    UserOptimizationPreferences,
)
from app.services.multi_objective_optimizer import (
    CANDIDATE_BASE_PROFILES,
    MultiObjectiveOptimizer,
)
from app.services.multi_objective_service import MultiObjectiveService


# ---------------------------------------------------------------------------
# Database & Client Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_client(test_db_engine):
    from app.core.deps import get_current_user_id
    from app.db.session import get_db

    test_user_id = uuid.uuid4()

    def override_get_db():
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = lambda: test_user_id
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Objective Space Tests
# ---------------------------------------------------------------------------

def test_eight_objective_vector_normalized():
    """Verifies that all 8 objectives are defined and strictly normalized in [0.0, 1.0]."""
    for cand, prof in CANDIDATE_BASE_PROFILES.items():
        vec = MultiObjectiveOptimizer.compute_objective_vector(
            candidate=cand,
            profile=prof,
            context_features={"baseline_bfi": 50.0, "recent_interruptions": 1.0},
            constraints_cfg={},
        )
        d = vec.to_dict()
        assert len(d) == 8
        for k, v in d.items():
            assert 0.0 <= v <= 1.0, f"Objective {k} for {cand} out of bounds: {v}"

    # Verify No-Intervention has perfect notification economy and interruption comfort
    no_act_vec = MultiObjectiveOptimizer.compute_objective_vector(
        candidate=CandidateIntervention.NO_INTERVENTION,
        profile=CANDIDATE_BASE_PROFILES[CandidateIntervention.NO_INTERVENTION],
        context_features={},
        constraints_cfg={},
    )
    assert no_act_vec.notification_economy == 1.0
    assert no_act_vec.interruption_comfort == 1.0


# ---------------------------------------------------------------------------
# 2. Hard Constraints Gating Tests
# ---------------------------------------------------------------------------

def test_hard_constraint_quiet_hours_filtering():
    """Verifies that notification-based interventions are strictly filtered during quiet hours."""
    # 23:30 is inside quiet hours (22:00-08:00)
    night_time = datetime(2026, 11, 25, 23, 30, 0, tzinfo=timezone.utc)
    audit, violations = MultiObjectiveOptimizer.evaluate_hard_constraints(
        eval_time=night_time,
        features={},
        constraints_cfg={"quiet_hours_enabled": True, "quiet_hours_start": 22, "quiet_hours_end": 8},
    )

    qh_status = next(s for s in audit if s.constraint_type == HardConstraintType.QUIET_HOURS)
    assert qh_status.passed is False

    # Notifications MUST be violated
    assert len(violations[CandidateIntervention.IMMEDIATE_REMINDER]) > 0
    assert len(violations[CandidateIntervention.DELAYED_REMINDER]) > 0

    # No-Intervention and Recovery Buffer MUST NOT be violated by quiet hours
    assert len(violations[CandidateIntervention.NO_INTERVENTION]) == 0
    assert len(violations[CandidateIntervention.SHORT_RECOVERY_BUFFER]) == 0


def test_hard_constraint_notification_quota_filtering():
    """Verifies that exceeding daily or hourly notification limit suppresses reminders."""
    day_time = datetime(2026, 11, 25, 14, 0, 0, tzinfo=timezone.utc)
    audit, violations = MultiObjectiveOptimizer.evaluate_hard_constraints(
        eval_time=day_time,
        features={},
        constraints_cfg={
            "quiet_hours_enabled": False,
            "max_notifications_per_day": 5,
            "notifications_sent_today": 5,
        },
    )

    quota_status = next(s for s in audit if s.constraint_type == HardConstraintType.MAX_NOTIFICATION_FREQUENCY)
    assert quota_status.passed is False
    assert len(violations[CandidateIntervention.IMMEDIATE_REMINDER]) > 0
    assert len(violations[CandidateIntervention.DELAYED_REMINDER]) > 0


def test_hard_constraint_calendar_availability_filtering():
    """Verifies that full calendar blocks filter rescheduling and focus sessions."""
    day_time = datetime(2026, 11, 25, 11, 0, 0, tzinfo=timezone.utc)
    audit, violations = MultiObjectiveOptimizer.evaluate_hard_constraints(
        eval_time=day_time,
        features={},
        constraints_cfg={"calendar_fully_booked": True},
    )

    cal_status = next(s for s in audit if s.constraint_type == HardConstraintType.CALENDAR_AVAILABILITY)
    assert cal_status.passed is False
    assert len(violations[CandidateIntervention.CALENDAR_RESCHEDULING]) > 0
    assert len(violations[CandidateIntervention.FOCUS_SESSION_RECOMMENDATION]) > 0


def test_hard_constraint_user_opt_out():
    """Verifies that explicit user opt-outs are strictly respected."""
    day_time = datetime(2026, 11, 25, 11, 0, 0, tzinfo=timezone.utc)
    audit, violations = MultiObjectiveOptimizer.evaluate_hard_constraints(
        eval_time=day_time,
        features={},
        constraints_cfg={"opted_out_interventions": ["break_large_task"]},
    )
    assert len(violations[CandidateIntervention.BREAK_LARGE_TASK]) > 0


# ---------------------------------------------------------------------------
# 3. Context-Dependent Weight Adaptation Tests
# ---------------------------------------------------------------------------

def test_context_weight_adaptation_fatigue():
    """Verifies that high cognitive fatigue shifts weights to recovery and friction reduction."""
    base_w = ObjectiveWeights()
    adapted_w, adaptations = MultiObjectiveOptimizer.adapt_weights_for_context(
        base_weights=base_w,
        context_features={"baseline_bfi": 75.0},
        eval_time=datetime.now(timezone.utc),
    )

    assert adapted_w.recovery_duration > base_w.recovery_duration
    assert adapted_w.behavioral_friction > base_w.behavioral_friction
    assert adapted_w.task_completion < base_w.task_completion
    assert len(adaptations) >= 1
    # Normalized sum to 1.0
    total = sum(adapted_w.model_dump().values())
    assert math.isclose(total, 1.0, abs_tol=1e-3)


def test_context_weight_adaptation_imminent_deadline():
    """Verifies that imminent deadline prioritizes task completion and resumption."""
    base_w = ObjectiveWeights()
    adapted_w, adaptations = MultiObjectiveOptimizer.adapt_weights_for_context(
        base_weights=base_w,
        context_features={"due_in_minutes": 30.0},
        eval_time=datetime.now(timezone.utc),
    )

    assert adapted_w.task_completion > base_w.task_completion
    assert adapted_w.task_resumption > base_w.task_resumption
    assert any("Imminent Deadline" in a for a in adaptations)


# ---------------------------------------------------------------------------
# 4. Pareto Dominance Analysis Tests
# ---------------------------------------------------------------------------

def test_pareto_frontier_determination():
    """Verifies multi-dimensional Pareto dominance identification."""
    req = MultiObjectiveOptimizationRequest(
        current_time=datetime(2026, 11, 25, 14, 0, 0, tzinfo=timezone.utc),
        user_constraints={"quiet_hours_enabled": False},
    )
    resp = MultiObjectiveOptimizer.optimize(req)

    assert len(resp.pareto_frontier) >= 1
    # Every candidate on the Pareto frontier must have pareto_rank == 1 and is_pareto_optimal == True
    for c in resp.pareto_frontier:
        assert c.is_pareto_optimal is True
        assert c.pareto_rank == 1
        assert len(c.dominated_by) == 0

    # No-Intervention has perfect notification economy (1.0) and comfort (1.0), so it is non-dominated
    no_act = next(c for c in resp.all_evaluated_candidates if c.candidate == CandidateIntervention.NO_INTERVENTION)
    assert no_act.is_pareto_optimal is True


# ---------------------------------------------------------------------------
# 5. First-Class No-Action Option & Fallback Tests
# ---------------------------------------------------------------------------

def test_no_action_selected_when_all_active_infeasible():
    """Verifies that No-Action is selected if all active interventions violate constraints."""
    night_time = datetime(2026, 11, 25, 23, 0, 0, tzinfo=timezone.utc)
    req = MultiObjectiveOptimizationRequest(
        current_time=night_time,
        user_constraints={
            "quiet_hours_enabled": True,
            "quiet_hours_start": 22,
            "quiet_hours_end": 8,
            "calendar_fully_booked": True,
            "opted_out_interventions": ["break_large_task", "short_recovery_buffer"],
        },
    )
    resp = MultiObjectiveOptimizer.optimize(req)
    assert resp.selected_intervention == CandidateIntervention.NO_INTERVENTION
    assert resp.is_no_action is True
    assert "satisfied all hard constraints" in resp.selection_rationale


def test_no_action_selected_when_utility_lift_is_negligible():
    """Verifies that No-Action is preferred when net utility lift is below threshold."""
    day_time = datetime(2026, 11, 25, 14, 0, 0, tzinfo=timezone.utc)
    req = MultiObjectiveOptimizationRequest(
        current_time=day_time,
        min_utility_lift_threshold=0.50,  # Unreasonably high threshold
    )
    resp = MultiObjectiveOptimizer.optimize(req)
    assert resp.selected_intervention == CandidateIntervention.NO_INTERVENTION
    assert resp.is_no_action is True
    assert "marginal net utility lift" in resp.selection_rationale


def test_no_action_selected_when_uncertainty_is_excessive():
    """Verifies safe fallback to No-Action when prediction uncertainty exceeds tolerance."""
    day_time = datetime(2026, 11, 25, 14, 0, 0, tzinfo=timezone.utc)
    req = MultiObjectiveOptimizationRequest(
        current_time=day_time,
        strict_uncertainty_threshold=0.05,  # Very strict uncertainty threshold
    )
    resp = MultiObjectiveOptimizer.optimize(req)
    assert resp.selected_intervention == CandidateIntervention.NO_INTERVENTION
    assert resp.is_no_action is True
    assert "uncertainty" in resp.selection_rationale


# ---------------------------------------------------------------------------
# 6. User Preference Customization Tests
# ---------------------------------------------------------------------------

def test_user_preference_weight_shifts_decision():
    """Verifies that shifting user weights changes the chosen optimal champion."""
    day_time = datetime(2026, 11, 25, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Completion-heavy preference
    req_completion = MultiObjectiveOptimizationRequest(
        current_time=day_time,
        custom_weights=ObjectiveWeights(
            task_completion=0.80,
            task_resumption=0.10,
            recovery_duration=0.02,
            behavioral_friction=0.02,
            notification_economy=0.02,
            interruption_comfort=0.02,
            user_preferences=0.01,
            schedule_feasibility=0.01,
        ),
        user_constraints={"quiet_hours_enabled": False},
    )
    resp_comp = MultiObjectiveOptimizer.optimize(req_completion)
    assert resp_comp.selected_intervention in (
        CandidateIntervention.FOCUS_SESSION_RECOMMENDATION,
        CandidateIntervention.IMMEDIATE_REMINDER,
        CandidateIntervention.CALENDAR_RESCHEDULING,
    )

    # 2. Recovery & Friction-heavy preference
    req_recovery = MultiObjectiveOptimizationRequest(
        current_time=day_time,
        custom_weights=ObjectiveWeights(
            task_completion=0.05,
            task_resumption=0.05,
            recovery_duration=0.50,
            behavioral_friction=0.30,
            notification_economy=0.05,
            interruption_comfort=0.05,
            user_preferences=0.0,
            schedule_feasibility=0.0,
        ),
        user_constraints={"quiet_hours_enabled": False},
    )
    resp_rec = MultiObjectiveOptimizer.optimize(req_recovery)
    assert resp_rec.selected_intervention == CandidateIntervention.SHORT_RECOVERY_BUFFER


# ---------------------------------------------------------------------------
# 7. Safety Authorization Boundary Tests
# ---------------------------------------------------------------------------

def test_safety_authorization_flag_strictly_true():
    """Verifies that all optimization outputs are flagged as proposal-only requiring authorization."""
    req = MultiObjectiveOptimizationRequest()
    resp = MultiObjectiveOptimizer.optimize(req)
    assert resp.requires_authorization is True


# ---------------------------------------------------------------------------
# 8. High-Level Service & Catalogs Tests
# ---------------------------------------------------------------------------

def test_service_list_objectives_and_constraints():
    """Verifies service listings for objectives and hard constraints."""
    objectives = MultiObjectiveService.list_objectives()
    assert len(objectives) == 8
    obj_ids = [o["id"] for o in objectives]
    assert OptimizationObjective.TASK_COMPLETION.value in obj_ids
    assert OptimizationObjective.NOTIFICATION_ECONOMY.value in obj_ids

    constraints = MultiObjectiveService.list_constraints()
    assert len(constraints) == 7
    c_ids = [c["id"] for c in constraints]
    assert HardConstraintType.QUIET_HOURS.value in c_ids
    assert HardConstraintType.MAX_NOTIFICATION_FREQUENCY.value in c_ids
    assert HardConstraintType.CALENDAR_AVAILABILITY.value in c_ids


def test_service_preferences_crud():
    """Verifies retrieval and update of user optimization preferences."""
    user_id = uuid.uuid4()
    pref = MultiObjectiveService.get_user_preferences(user_id=user_id)
    assert pref.user_id == user_id
    assert pref.max_daily_interventions == 8

    # Update preferences
    pref.preferred_weights.recovery_duration = 0.40
    pref.opted_out_interventions = [CandidateIntervention.CALENDAR_RESCHEDULING]
    updated = MultiObjectiveService.update_user_preferences(preferences=pref)
    assert updated.opted_out_interventions == [CandidateIntervention.CALENDAR_RESCHEDULING]
    assert updated.preferred_weights.recovery_duration > 0.20


# ---------------------------------------------------------------------------
# 9. REST API Integration Tests
# ---------------------------------------------------------------------------

def test_api_list_objectives_and_constraints(test_client):
    """GET /api/v1/optimization/objectives and /constraints."""
    resp_obj = test_client.get("/api/v1/optimization/objectives")
    assert resp_obj.status_code == 200
    assert len(resp_obj.json()) == 8

    resp_c = test_client.get("/api/v1/optimization/constraints")
    assert resp_c.status_code == 200
    assert len(resp_c.json()) == 7


def test_api_optimize_post(test_client):
    """POST /api/v1/optimization/optimize."""
    user_id = str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "context_features": {"baseline_bfi": 52.0, "recent_interruptions": 1.0},
        "user_constraints": {"quiet_hours_enabled": False},
    }
    resp = test_client.post("/api/v1/optimization/optimize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "optimization_id" in data
    assert "selected_intervention" in data
    assert "pareto_frontier" in data
    assert "applied_constraints" in data
    assert data["requires_authorization"] is True


def test_api_optimize_get(test_client):
    """GET /api/v1/optimization/optimize."""
    resp = test_client.get("/api/v1/optimization/optimize")
    assert resp.status_code == 200
    data = resp.json()
    assert "selected_intervention" in data
    assert data["requires_authorization"] is True


def test_api_preferences_get_and_put(test_client):
    """GET and PUT /api/v1/optimization/preferences."""
    resp_get = test_client.get("/api/v1/optimization/preferences")
    assert resp_get.status_code == 200
    pref_data = resp_get.json()
    assert "preferred_weights" in pref_data

    # Update
    pref_data["max_daily_interventions"] = 12
    resp_put = test_client.put("/api/v1/optimization/preferences", json=pref_data)
    assert resp_put.status_code == 200
    assert resp_put.json()["max_daily_interventions"] == 12


def test_api_analytics_optimize(test_client):
    """GET /api/v1/analytics/optimization/optimize."""
    resp = test_client.get("/api/v1/analytics/optimization/optimize")
    assert resp.status_code == 200
    data = resp.json()
    assert "selected_intervention" in data
    assert "selection_rationale" in data
