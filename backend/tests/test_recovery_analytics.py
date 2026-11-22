"""
Unit and integration test suite for Automated Cognitive Recovery and Micro-Delay
Analytics (ContextIQ Phase 3.7).
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
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, InterruptionSeverity, TaskStatus
from app.models.interruption import Interruption, InterruptionType
from app.models.task import Task
from app.models.user import User
from app.services.recovery_analytics import RecoveryAnalyticsService
from app.services.temporal_feature_extractor import TemporalFeatureExtractor


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit Tests for Recovery Analytics Engine
# ---------------------------------------------------------------------------

def test_three_tier_resumption_delay():
    """
    Verifies that the engine distinguishes:
    1. Return-to-device delay (from session resume_delay)
    2. Return-to-app delay (from detected interruptions)
    3. Confirmed task resumption delay (when task context is verified)
    """
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    t0 = datetime.now(timezone.utc) - timedelta(days=2)

    with Session(engine) as session:
        user = User(id=user_id, email=f"delay_{user_id.hex[:6]}@example.com", display_name="Delay User")
        session.add(user)
        task = Task(id=task_id, user_id=user_id, title="Core Task")
        session.add(task)

        # 1. Detected interruption with 12.5s return-to-app delay
        di = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            severity=InterruptionSeverity.MEDIUM,
            start_timestamp=t0,
            duration_seconds=45.0,
            primary_app="code.exe",
            interrupting_app="slack.exe",
            resumption_lag_seconds=12.5,
            explanation="Test app return",
        )
        session.add(di)

        # 2. Session with confirmed task resumption of 25.0s
        cs = ContextSession(
            user_id=user_id,
            task_id=task_id,
            started_at=t0 + timedelta(hours=1),
            ended_at=t0 + timedelta(hours=2),
            focused_time_seconds=3000.0,
            resume_delay_seconds=25.0,
            task_association_status="EXPLICIT",
        )
        session.add(cs)
        session.commit()

        metrics = RecoveryAnalyticsService.get_recovery_metrics(
            db=session, user_id=user_id, period_days=7
        )

        tiers = metrics.delays_by_tier
        assert tiers.return_to_app_delay_seconds == 12.5
        assert tiers.return_to_device_delay_seconds == 25.0
        assert tiers.confirmed_task_resumption_delay_seconds == 25.0
        assert tiers.is_estimated is False  # Confirmed task resumption was available
        assert tiers.sample_count == 2
        assert "Behavioral proxies" in metrics.disclaimer


def test_advanced_recovery_metrics_statistics():
    """
    Tests mean, median, standard deviation, interruption frequency,
    and consecutive interruption clusters (< 5 minutes apart).
    """
    user_id = uuid.uuid4()
    t0 = datetime.now(timezone.utc) - timedelta(days=1)

    with Session(engine) as session:
        user = User(id=user_id, email=f"stats_{user_id.hex[:6]}@example.com", display_name="Stats User")
        session.add(user)

        # Create 3 interruptions: 10s, 20s, 30s resumption lags
        # Int 1 and Int 2 are 2 minutes apart (cluster of 2)
        di1 = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=t0,
            resumption_lag_seconds=10.0,
            explanation="Int 1",
        )
        di2 = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=t0 + timedelta(minutes=2),
            resumption_lag_seconds=20.0,
            explanation="Int 2",
        )
        di3 = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=t0 + timedelta(hours=3),
            resumption_lag_seconds=30.0,
            explanation="Int 3",
        )
        session.add_all([di1, di2, di3])

        # Active session: 1 hour (3600s focused)
        cs = ContextSession(
            user_id=user_id,
            started_at=t0 - timedelta(minutes=10),
            ended_at=t0 + timedelta(hours=4),
            focused_time_seconds=3600.0,
            interruption_time_seconds=300.0,
            transition_count=5,
        )
        session.add(cs)
        session.commit()

        metrics = RecoveryAnalyticsService.get_recovery_metrics(
            db=session, user_id=user_id, period_days=7
        )

        assert metrics.mean_resumption_lag_seconds == 20.0
        assert metrics.median_resumption_lag_seconds == 20.0
        assert metrics.recovery_time_variability == 10.0
        assert metrics.consecutive_interruption_count == 2
        assert metrics.interruption_frequency > 0.0


def test_behavioral_friction_index():
    """
    Verifies that the Behavioral Friction Index:
    1. Stays bounded within [0, 100].
    2. Correctly incorporates task forgetting, interruption, context switches, recovery delay, and variability.
    3. Prevents double-counting by utilizing session active time.
    """
    user_id = uuid.uuid4()
    t0 = datetime.now(timezone.utc) - timedelta(days=5)

    with Session(engine) as session:
        user = User(id=user_id, email=f"bfi_{user_id.hex[:6]}@example.com", display_name="BFI User")
        session.add(user)

        # 1 forgotten task out of 2 resolved -> 50% forgetting rate
        t1 = Task(user_id=user_id, title="T1", status=TaskStatus.COMPLETED, created_at=t0)
        t2 = Task(user_id=user_id, title="T2", status=TaskStatus.FORGOTTEN, created_at=t0)
        session.add_all([t1, t2])

        # Session with moderate switching and resume delay
        cs = ContextSession(
            user_id=user_id,
            started_at=t0,
            ended_at=t0 + timedelta(hours=2),
            focused_time_seconds=6000.0,
            interruption_time_seconds=600.0,
            transition_count=4,
            resume_delay_seconds=600.0,  # 10 minutes delay
        )
        session.add(cs)
        session.commit()

        bfi = RecoveryAnalyticsService.get_behavioral_friction_index(
            db=session, user_id=user_id, period_days=14
        )

        assert 0.0 <= bfi.overall_score <= 100.0
        assert bfi.forgetting_score == 50.0
        assert bfi.telemetry_adjusted is True
        assert len(bfi.contributing_factors) >= 1


def test_interruption_trends_contextual_breakdown():
    """Verifies circadian, weekly, and app breakdowns, enforcing min 3 observation guardrails."""
    user_id = uuid.uuid4()
    # Wednesday morning at 10:00 AM UTC
    t0 = datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"trend_{user_id.hex[:6]}@example.com", display_name="Trend User")
        session.add(user)

        # Add 3 interruptions on Wednesday morning in slack.exe
        for i in range(3):
            di = DetectedInterruption(
                user_id=user_id,
                interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
                start_timestamp=t0 + timedelta(minutes=i * 20),
                interrupting_app="slack.exe",
                resumption_lag_seconds=15.0,
                explanation="Slack switch",
            )
            session.add(di)
        session.commit()

        trends = RecoveryAnalyticsService.get_interruption_trends(
            db=session, user_id=user_id, period_days=30, now=t0 + timedelta(days=1)
        )

        # Morning bucket has 3 observations -> sufficient data
        morning = trends.by_time_of_day["Morning (06:00-12:00)"]
        assert morning.observation_count == 3
        assert morning.insufficient_data is False
        assert morning.mean_resumption_lag_seconds == 15.0

        # Evening bucket has 0 observations -> insufficient data
        evening = trends.by_time_of_day["Evening (17:00-22:00)"]
        assert evening.observation_count == 0
        assert evening.insufficient_data is True


def test_personal_baseline_and_trend_direction():
    """
    Verifies that the user's recent behavior is evaluated against their own
    historical baseline (e.g. 14 days), computing ratios without comparing
    against other users.
    """
    user_id = uuid.uuid4()
    now_dt = datetime.now(timezone.utc)
    t_hist = now_dt - timedelta(days=10)
    t_recent = now_dt - timedelta(days=1)

    with Session(engine) as session:
        user = User(id=user_id, email=f"base_{user_id.hex[:6]}@example.com", display_name="Base User")
        session.add(user)

        # Historical baseline: 3 interruptions with fast 10s recovery
        for i in range(3):
            di_hist = DetectedInterruption(
                user_id=user_id,
                interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
                start_timestamp=t_hist + timedelta(hours=i),
                resumption_lag_seconds=10.0,
                explanation="Historical",
            )
            session.add(di_hist)

        # Recent period: 3 interruptions with slow 25s recovery (2.5x slower)
        for i in range(3):
            di_rec = DetectedInterruption(
                user_id=user_id,
                interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
                start_timestamp=t_recent + timedelta(hours=i),
                resumption_lag_seconds=25.0,
                explanation="Recent",
            )
            session.add(di_rec)

        session.commit()

        baseline = RecoveryAnalyticsService.get_personal_baseline(
            db=session,
            user_id=user_id,
            baseline_period_days=14,
            current_period_days=3,
            now=now_dt,
        )

        assert baseline.has_sufficient_history is True
        assert baseline.baseline_mean_resumption_lag is not None
        assert baseline.current_mean_resumption_lag is not None
        assert baseline.resumption_lag_ratio is not None
        assert baseline.trend_direction in ("ELEVATED_FRICTION", "STABLE", "IMPROVING")


def test_cold_start_and_missing_data_safety():
    """Verifies that an empty profile / cold start returns graceful, safe defaults."""
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"empty_{user_id.hex[:6]}@example.com", display_name="Empty User")
        session.add(user)
        session.commit()

        metrics = RecoveryAnalyticsService.get_recovery_metrics(db=session, user_id=user_id)
        assert metrics.mean_resumption_lag_seconds is None
        assert metrics.interruption_frequency == 0.0

        bfi = RecoveryAnalyticsService.get_behavioral_friction_index(db=session, user_id=user_id)
        assert bfi.overall_score == 0.0

        baseline = RecoveryAnalyticsService.get_personal_baseline(db=session, user_id=user_id)
        assert baseline.has_sufficient_history is False
        assert baseline.trend_direction == "INSUFFICIENT_DATA"


def test_temporal_feature_extractor_leakage_safety():
    """
    Verifies that TemporalFeatureExtractor computes features strictly prior
    to as_of timestamp, asserting zero data leakage.
    """
    user_id = uuid.uuid4()
    as_of = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(id=user_id, email=f"ml_{user_id.hex[:6]}@example.com", display_name="ML User")
        session.add(user)

        # 1. Past interruption (10:00 AM) -> MUST be included
        past_di = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=as_of - timedelta(hours=2),
            resumption_lag_seconds=20.0,
            explanation="Past",
        )
        # 2. Future interruption (2:00 PM) -> MUST NOT be included (leakage check)
        future_di = DetectedInterruption(
            user_id=user_id,
            interruption_type=DetectedInterruptionType.APPLICATION_SWITCH,
            start_timestamp=as_of + timedelta(hours=2),
            resumption_lag_seconds=999.0,
            explanation="Future Leakage",
        )
        session.add_all([past_di, future_di])
        session.commit()

        feats = TemporalFeatureExtractor.extract_features_for_task(
            db=session, user_id=user_id, as_of=as_of
        )

        assert feats["avg_resumption_lag_seconds"] == 20.0
        assert feats["feature_schema_version"] == "v2.3"
        assert feats["recent_interruption_frequency"] == 1.0  # Only past one counted


# ---------------------------------------------------------------------------
# Integration Tests with FastAPI Endpoints
# ---------------------------------------------------------------------------

def test_api_analytics_endpoints(client):
    user_id = uuid.uuid4()
    with Session(engine) as session:
        user = User(id=user_id, email=f"api_{user_id.hex[:6]}@example.com", display_name="API User")
        session.add(user)
        session.commit()

    headers = {"X-User-ID": str(user_id)}

    # 1. Recovery Endpoint
    rec_resp = client.get("/api/v1/analytics/recovery", headers=headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert "interruption_frequency" in rec_data
    assert "delays_by_tier" in rec_data

    # 2. Friction Endpoint
    fric_resp = client.get("/api/v1/analytics/friction", headers=headers)
    assert fric_resp.status_code == 200
    fric_data = fric_resp.json()
    assert "overall_score" in fric_data
    assert fric_data["telemetry_adjusted"] is True

    # 3. Interruption Trends Endpoint
    trends_resp = client.get("/api/v1/analytics/interruption-trends", headers=headers)
    assert trends_resp.status_code == 200
    trends_data = trends_resp.json()
    assert "by_time_of_day" in trends_data
    assert "by_day_of_week" in trends_data

    # 4. Personal Baseline Endpoint
    base_resp = client.get("/api/v1/analytics/personal-baseline", headers=headers)
    assert base_resp.status_code == 200
    base_data = base_resp.json()
    assert "trend_direction" in base_data
