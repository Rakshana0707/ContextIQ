"""
Integration and Unit Tests for ContextIQ Phase 3.8:
Automated Telemetry Integration with Predictive Intelligence.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test_telemetry.db")

# Register SQLite compilation for Postgres JSONB in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import app.models  # Register all models on Base
from app.db.session import Base, engine
from app.main import app
from app.models.context_session import ContextSession
from app.models.detected_interruption import (
    DetectedInterruption,
    DetectedInterruptionFeedback,
)
from app.models.enums import (
    DetectedInterruptionType,
    InterruptionFeedbackClassification,
    RecommendationFeedbackAction,
    RecommendationStatus,
    RecommendationType,
    TaskPriority,
    TaskStatus,
)
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.recommendation import Recommendation
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.task import Task
from app.models.task_event import TaskEvent, TaskEventType
from app.models.user import User
from app.schemas.prediction import RiskCategory, TelemetryCoverageStatus
from app.services.feedback_loop_service import FeedbackLoopService
from app.services.prediction_service import PredictionService
from app.services.temporal_feature_extractor import TemporalFeatureExtractor


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. End-to-End Prediction Pipeline & Explainability Tests
# ---------------------------------------------------------------------------

def test_end_to_end_prediction_with_telemetry():
    """
    Verifies that the full pipeline:
    Raw Telemetry -> Interruption -> Sessions -> Temporal Features -> Prediction -> Survival -> Reasons
    successfully executes and yields calibrated metrics.
    """
    user_id = uuid.uuid4()
    now = datetime(2026, 11, 22, 14, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"user_{user_id.hex[:6]}@example.com", display_name="Test User")
        session.add(user)

        # 1. Insert Raw Telemetry Events
        for i in range(10):
            ev = RawTelemetryEvent(
                event_id=f"evt_{user_id.hex[:6]}_{i}",
                user_id=user_id,
                device_id="desktop_win_01",
                event_type="application_activated" if i % 2 == 0 else "user_active_returned",
                event_timestamp=now - timedelta(hours=i % 6, minutes=i * 5),
                application_identifier="code.exe" if i % 2 == 0 else "chrome.exe",
            )
            session.add(ev)

        # 2. Insert Detected Interruptions with Resumption Lags
        for i in range(4):
            di = DetectedInterruption(
                user_id=user_id,
                interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
                start_timestamp=now - timedelta(hours=1, minutes=i * 12),
                end_timestamp=now - timedelta(hours=1, minutes=i * 12 - 2),
                duration_seconds=120.0,
                resumption_lag_seconds=42.0 + (i * 8.0),
                metadata_payload={"return_to_app_delay_seconds": 35.0},
                explanation=f"Interruption {i}",
            )
            session.add(di)

        # 3. Insert Reconstructed Work Session
        cs = ContextSession(
            user_id=user_id,
            started_at=now - timedelta(hours=4),
            ended_at=now - timedelta(hours=1),
            focused_time_seconds=9000.0,
            interruption_time_seconds=1800.0,
            interruption_count=4,
            transition_count=12,
            resume_delay_seconds=45.0,
        )
        session.add(cs)

        # 4. Create Task
        task = Task(
            user_id=user_id,
            title="Implement predictive telemetry integration",
            priority=TaskPriority.HIGH,
            context_tag="work_coding",
            due_at=now + timedelta(hours=12),
            created_at=now - timedelta(hours=2),
        )
        session.add(task)
        session.commit()

        # Run Prediction Service
        pred = PredictionService.predict_for_task(
            db=session, user_id=user_id, task_id=task.id, as_of=now
        )

        assert pred.task_id == str(task.id)
        assert 0.05 <= pred.forgetting_probability <= 0.95
        assert pred.risk_category in (RiskCategory.LOW, RiskCategory.MEDIUM, RiskCategory.HIGH, RiskCategory.CRITICAL)
        assert pred.feature_availability.telemetry_coverage in (
            TelemetryCoverageStatus.FULL,
            TelemetryCoverageStatus.PARTIAL,
        )
        assert pred.feature_availability.is_cold_start is False
        assert pred.confidence_score >= 0.80

        # Behavioral indicators reflect observed telemetry
        assert pred.behavioral_indicators.recent_interruption_frequency >= 4.0
        assert pred.behavioral_indicators.median_resumption_lag_seconds >= 40.0
        assert pred.behavioral_indicators.behavioral_friction_index > 0.0

        # Multi-Horizon Survival Estimates S(t)
        assert len(pred.survival_estimates) == 5
        # Verify monotonicity: S(6h) >= S(12h) >= S(24h) >= S(48h) >= S(168h)
        for j in range(len(pred.survival_estimates) - 1):
            assert (
                pred.survival_estimates[j].survival_probability
                >= pred.survival_estimates[j + 1].survival_probability
            )

        # Cognitive Disclaimer Check
        assert "mental state measurements" in pred.cognitive_disclaimer
        assert "observable application" in pred.cognitive_disclaimer

        # Check that reasons contain telemetry-based evidence
        reasons_text = " ".join(r.description for r in pred.reasons)
        assert "interruption" in reasons_text.lower() or "friction" in reasons_text.lower()


# ---------------------------------------------------------------------------
# 2. Strict Temporal Leakage Prevention Tests
# ---------------------------------------------------------------------------

def test_strict_temporal_leakage_prevention():
    """
    Asserts that events occurring at or after `as_of` do NOT alter the extracted
    feature vector or prediction results.
    """
    user_id = uuid.uuid4()
    as_of = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"leakage_{user_id.hex[:6]}@example.com", display_name="Leakage User")
        session.add(user)

        # Past events before as_of (9:00 AM)
        past_di = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=as_of - timedelta(hours=1),
            resumption_lag_seconds=25.0,
            duration_seconds=60.0,
            explanation="Past Interruption",
        )
        session.add(past_di)

        task = Task(
            user_id=user_id,
            title="Leakage Test Task",
            priority=TaskPriority.MEDIUM,
            created_at=as_of,
        )
        session.add(task)
        session.commit()

        # Extract features at as_of
        feats_initial = TemporalFeatureExtractor.extract_features_for_task(
            db=session, user_id=user_id, as_of=as_of
        )
        pred_initial = PredictionService.predict_for_task(
            db=session, user_id=user_id, task_id=task.id, as_of=as_of
        )

        # Now insert FUTURE events after as_of (e.g. 11:00 AM and 2:00 PM)
        future_event = RawTelemetryEvent(
            event_id=f"future_ev_{user_id.hex[:6]}",
            user_id=user_id,
            event_type="application_activated",
            event_timestamp=as_of + timedelta(hours=1),
            application_identifier="youtube.exe",
        )
        future_di = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.SESSION_DISRUPTION,
            start_timestamp=as_of + timedelta(hours=4),
            resumption_lag_seconds=999.0,
            duration_seconds=3600.0,
            explanation="Future Interruption that MUST be ignored",
        )
        future_te = TaskEvent(
            task_id=task.id,
            user_id=user_id,
            event_type=TaskEventType.COMPLETED,
            occurred_at=as_of + timedelta(hours=5),
        )
        session.add_all([future_event, future_di, future_te])
        session.commit()

        # Re-extract features strictly as-of T
        feats_after_future_events = TemporalFeatureExtractor.extract_features_for_task(
            db=session, user_id=user_id, as_of=as_of
        )
        pred_after_future_events = PredictionService.predict_for_task(
            db=session, user_id=user_id, task_id=task.id, as_of=as_of
        )

        # Assert zero leakage
        assert (
            feats_initial["recent_interruption_frequency"]
            == feats_after_future_events["recent_interruption_frequency"]
        )
        assert (
            feats_initial["avg_resumption_lag_seconds"]
            == feats_after_future_events["avg_resumption_lag_seconds"]
        )
        assert (
            pred_initial.forgetting_probability
            == pred_after_future_events.forgetting_probability
        )
        assert (
            pred_initial.risk_category
            == pred_after_future_events.risk_category
        )


# ---------------------------------------------------------------------------
# 3. Cold-Start and Missing Telemetry Handling Tests
# ---------------------------------------------------------------------------

def test_cold_start_handling():
    """
    Verifies that for users without desktop agent or insufficient history:
    1. Coverage is flagged as INSUFFICIENT_HISTORY.
    2. Cold-start is True.
    3. Missing data is NOT assumed to mean zero interruptions; population defaults are imputed.
    4. A confidence discount is applied.
    5. The explainability layer explicitly warns about baseline fallback.
    """
    user_id = uuid.uuid4()
    now = datetime(2026, 11, 22, 15, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"cold_{user_id.hex[:6]}@example.com", display_name="Cold Start User")
        session.add(user)

        # Create Task with ZERO telemetry and ZERO session records
        task = Task(
            user_id=user_id,
            title="Cold start task",
            priority=TaskPriority.LOW,
            created_at=now,
        )
        session.add(task)
        session.commit()

        pred = PredictionService.predict_for_task(
            db=session, user_id=user_id, task_id=task.id, as_of=now
        )

        assert pred.feature_availability.telemetry_coverage == TelemetryCoverageStatus.INSUFFICIENT_HISTORY
        assert pred.feature_availability.is_cold_start is True
        assert pred.confidence_discount_applied is True
        assert pred.confidence_score < 0.80

        # Features were imputed from population defaults, NOT zero
        assert pred.behavioral_indicators.recent_interruption_frequency == 1.5
        assert pred.behavioral_indicators.median_resumption_lag_seconds == 40.0
        assert "behavioral_friction_index" in pred.feature_availability.imputed_features

        # Explainability explicitly explains population baseline fallback
        baseline_reasons = [
            r for r in pred.reasons if "population baseline" in r.description.lower()
        ]
        assert len(baseline_reasons) > 0
        assert baseline_reasons[0].is_observed is False


# ---------------------------------------------------------------------------
# 4. Proactive Telemetry-Driven Recommendations Tests
# ---------------------------------------------------------------------------

def test_proactive_telemetry_recommendations():
    """
    Verifies that high friction or clustered disruptions generate proactive
    BREAK_SUGGESTION and BATCH_TASKS recommendations.
    """
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"rec_{user_id.hex[:6]}@example.com", display_name="Rec User")
        session.add(user)

        # Insert 4 closely spaced interruptions to trigger consecutive clustering
        for i in range(4):
            di = DetectedInterruption(
                user_id=user_id,
                interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
                start_timestamp=now - timedelta(minutes=10 - (i * 2)),
                end_timestamp=now - timedelta(minutes=9 - (i * 2)),
                duration_seconds=60.0,
                resumption_lag_seconds=65.0,
                explanation="Rapid cluster",
            )
            session.add(di)

        # Context session with high transitions (15 switches)
        cs = ContextSession(
            user_id=user_id,
            started_at=now - timedelta(hours=2),
            ended_at=now,
            focused_time_seconds=5000.0,
            interruption_time_seconds=2200.0,
            transition_count=16,
            resume_delay_seconds=60.0,
        )
        session.add(cs)

        task = Task(
            user_id=user_id,
            title="High Friction Task",
            priority=TaskPriority.HIGH,
            context_tag="deep_focus",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()

        # Trigger recommendations list
        client_test = TestClient(app)
        resp = client_test.get("/api/v1/recommendations", headers={"X-User-ID": str(user_id)})
        assert resp.status_code == 200
        recs = resp.json()

        rec_types = [r["recommendation_type"] for r in recs]
        assert "BREAK_SUGGESTION" in rec_types
        assert "BATCH_TASKS" in rec_types

        break_rec = next(r for r in recs if r["recommendation_type"] == "BREAK_SUGGESTION")
        assert "friction" in break_rec["message"].lower() or "reset" in break_rec["message"].lower()


# ---------------------------------------------------------------------------
# 5. Continuous Calibration & Feedback Loop Dataset Tests
# ---------------------------------------------------------------------------

def test_feedback_loop_dataset_export():
    """
    Verifies that user validation feedback on interruptions and task outcomes
    are gathered into candidate training datasets, and that automated production
    retraining is strictly disabled.
    """
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"fb_{user_id.hex[:6]}@example.com", display_name="Feedback User")
        session.add(user)

        # 1. Detected interruption with feedback
        di = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=now - timedelta(hours=3),
            resumption_lag_seconds=55.0,
            duration_seconds=120.0,
            explanation="Interruption with feedback",
        )
        session.add(di)
        session.flush()

        fb = DetectedInterruptionFeedback(
            interruption_id=di.id,
            user_id=user_id,
            feedback_classification=InterruptionFeedbackClassification.GENUINE_INTERRUPTION,
            notes="Accurate detection",
        )
        session.add(fb)

        # 2. Completed and Forgotten Tasks
        t_completed = Task(
            user_id=user_id,
            title="Completed Task",
            status=TaskStatus.COMPLETED,
            created_at=now - timedelta(days=1),
        )
        t_forgotten = Task(
            user_id=user_id,
            title="Forgotten Task",
            status=TaskStatus.FORGOTTEN,
            created_at=now - timedelta(days=2),
        )
        session.add_all([t_completed, t_forgotten])

        # 3. Recommendation Feedback
        rec = Recommendation(
            user_id=user_id,
            recommendation_type=RecommendationType.BREAK_SUGGESTION,
            title="Break Suggestion",
            message="Take a break",
            status=RecommendationStatus.PENDING,
        )
        session.add(rec)
        session.flush()

        rec_fb = RecommendationFeedback(
            recommendation_id=rec.id,
            user_id=user_id,
            action=RecommendationFeedbackAction.ACCEPTED,
            feedback_note="Good timing",
        )
        session.add(rec_fb)
        session.commit()

        dataset = FeedbackLoopService.export_candidate_training_dataset(
            db=session, user_id=user_id
        )

        assert dataset["auto_retraining_allowed"] is False
        assert dataset["total_candidate_samples"] >= 3
        assert len(dataset["interruption_feedback_samples"]) >= 1
        assert len(dataset["task_outcome_samples"]) >= 2
        assert len(dataset["recommendation_feedback_samples"]) >= 1

        # Check ground truth in export
        int_sample = dataset["interruption_feedback_samples"][0]
        assert int_sample["ground_truth_classification"] == "GENUINE_INTERRUPTION"
        assert int_sample["notes"] == "Accurate detection"


# ---------------------------------------------------------------------------
# 6. HTTP API Endpoint Verification Tests
# ---------------------------------------------------------------------------

def test_api_prediction_endpoints(client):
    """
    Verifies HTTP responses for:
    POST /api/v1/predictions/tasks/{task_id}/predict
    GET  /api/v1/predictions/tasks/{task_id}/survival
    GET  /api/v1/predictions/forgetting
    GET  /api/v1/analytics/feedback/candidate-dataset
    """
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"http_{user_id.hex[:6]}@example.com", display_name="HTTP User")
        session.add(user)

        task = Task(
            user_id=user_id,
            title="HTTP Test Task",
            priority=TaskPriority.HIGH,
            context_tag="anchor_test",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()
        task_id = str(task.id)

    headers = {"X-User-ID": str(user_id)}

    # 1. On-demand live prediction
    pred_res = client.post(f"/api/v1/predictions/tasks/{task_id}/predict", headers=headers)
    assert pred_res.status_code == 200
    data = pred_res.json()
    assert "forgetting_probability" in data
    assert "survival_estimates" in data
    assert "behavioral_indicators" in data
    assert "feature_availability" in data
    assert "cognitive_disclaimer" in data

    # 2. Task survival curve
    surv_res = client.get(f"/api/v1/predictions/tasks/{task_id}/survival", headers=headers)
    assert surv_res.status_code == 200
    surv_data = surv_res.json()
    assert isinstance(surv_data, list)
    assert len(surv_data) == 5
    assert surv_data[0]["horizon_hours"] == 6.0
    assert "survival_probability" in surv_data[0]

    # 3. List predictions (backward-compatible)
    list_res = client.get("/api/v1/predictions/forgetting", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data) >= 1
    assert "riskScore" in list_data[0]
    assert "riskLevel" in list_data[0]

    # 4. Candidate feedback dataset
    fb_res = client.get("/api/v1/analytics/feedback/candidate-dataset", headers=headers)
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["auto_retraining_allowed"] is False
    assert "total_candidate_samples" in fb_data
