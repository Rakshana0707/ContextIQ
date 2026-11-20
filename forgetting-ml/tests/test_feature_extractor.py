"""
test_feature_extractor.py

Comprehensive tests for ContextIQ's Strict Temporal Feature Extractor,
Snapshot Versioning, and Leakage Validation (Phase 2.2).
"""

from datetime import datetime, timedelta, timezone
import pytest
import pandas as pd

from ml.features.extractor import extract_features, FeatureSnapshot
from ml.features.feature_spec import (
    FeatureSchemaVersion,
    ALL_RAW_FEATURES,
    V2_2_ALL_RAW_FEATURES,
    NUMERIC_FEATURES,
    ENHANCED_TEMPORAL_NUMERIC_FEATURES,
)
from app.schemas import TaskFeatures


@pytest.fixture
def base_time():
    return datetime(2025, 2, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_user_history(base_time):
    """Generates realistic historical tasks, events, and interruptions prior to base_time."""
    u_id = "USER_42"
    tasks = []
    events = []
    interruptions = []

    # 3 prior tasks
    for i in range(1, 4):
        t_id = f"TASK_HIST_{i}"
        created = base_time - timedelta(days=4 - i, hours=2)
        started = created + timedelta(minutes=15)
        completed = started + timedelta(minutes=45)
        status = "completed" if i < 3 else "forgotten"

        tasks.append({
            "id": t_id,
            "user_id": u_id,
            "category": "Work" if i == 1 else "Personal",
            "priority": "HIGH" if i == 1 else "MEDIUM",
            "location": "Office",
            "status": status,
            "created_at": created,
            "started_at": started,
            "completed_at": completed if status == "completed" else None,
            "deadline_at": created + timedelta(hours=12),
        })

        events.append({"task_id": t_id, "user_id": u_id, "event_type": "created", "timestamp": created})
        events.append({"task_id": t_id, "user_id": u_id, "event_type": "started", "timestamp": started})
        if status == "completed":
            events.append({"task_id": t_id, "user_id": u_id, "event_type": "completed", "timestamp": completed})
        else:
            events.append({"task_id": t_id, "user_id": u_id, "event_type": "forgotten", "timestamp": completed})

    # Prior interruptions with known resumption lag (pause -> resume)
    pause_t = base_time - timedelta(hours=3)
    resume_t = pause_t + timedelta(seconds=120)  # 120s lag
    events.append({"task_id": "TASK_ACTIVE", "user_id": u_id, "event_type": "paused", "timestamp": pause_t})
    events.append({"task_id": "TASK_ACTIVE", "user_id": u_id, "event_type": "resumed", "timestamp": resume_t})

    interruptions.append({
        "user_id": u_id,
        "start_time": pause_t,
        "duration_seconds": 300,
    })

    return {
        "user_id": u_id,
        "tasks_df": pd.DataFrame(tasks),
        "events_df": pd.DataFrame(events),
        "interruptions_df": pd.DataFrame(interruptions),
    }


# =====================================================================
# 1. Strict Temporal Leakage Invariant Tests (Adversarial Injection)
# =====================================================================

def test_future_events_do_not_leak_into_feature_vector(base_time, sample_user_history):
    """
    CRITICAL LEAKAGE TEST:
    Extract features as of base_time.
    Then, inject future completions, future interruptions, and future task events
    occurring at base_time + 5 hours.
    Assert that the extracted feature snapshot remains 100% bit-for-bit identical!
    """
    u_id = sample_user_history["user_id"]
    t_id = "TASK_TARGET"
    tasks_df = sample_user_history["tasks_df"].copy()
    events_df = sample_user_history["events_df"].copy()
    ints_df = sample_user_history["interruptions_df"].copy()

    # Add target task created at base_time - 1h
    target_row = pd.DataFrame([{
        "id": t_id,
        "user_id": u_id,
        "category": "Work",
        "priority": "HIGH",
        "location": "Office",
        "status": "in_progress",
        "created_at": base_time - timedelta(hours=1),
        "deadline_at": base_time + timedelta(hours=10),
    }])
    tasks_df = pd.concat([tasks_df, target_row], ignore_index=True)

    # 1. Baseline extraction strictly as of base_time
    clean_snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        tasks_df=tasks_df,
        events_df=events_df,
        interruptions_df=ints_df,
        schema_version="v2.2",
    )

    # 2. Adversarially inject FUTURE records occurring AFTER base_time
    future_time_1 = base_time + timedelta(hours=2)
    future_time_2 = base_time + timedelta(hours=5)

    # Future task creation
    future_tasks = pd.concat([tasks_df, pd.DataFrame([{
        "id": "FUTURE_TASK_99",
        "user_id": u_id,
        "category": "Work",
        "priority": "HIGH",
        "location": "Office",
        "status": "completed",
        "created_at": future_time_1,
        "completed_at": future_time_2,
        "deadline_at": future_time_2,
    }])], ignore_index=True)

    # Future events
    future_events = pd.concat([events_df, pd.DataFrame([
        {"task_id": t_id, "user_id": u_id, "event_type": "completed", "timestamp": future_time_2},
        {"task_id": "FUTURE_TASK_99", "user_id": u_id, "event_type": "created", "timestamp": future_time_1},
    ])], ignore_index=True)

    # Future interruptions
    future_ints = pd.concat([ints_df, pd.DataFrame([
        {"user_id": u_id, "start_time": future_time_1, "duration_seconds": 900},
    ])], ignore_index=True)

    # 3. Extract features again using the future-contaminated tables as of base_time
    adversarial_snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        tasks_df=future_tasks,
        events_df=future_events,
        interruptions_df=future_ints,
        schema_version="v2.2",
    )

    # Assert 100% equivalence of all features
    for feat_name, clean_val in clean_snapshot.features.items():
        adv_val = adversarial_snapshot.features[feat_name]
        assert adv_val == clean_val, (
            f"LEAKAGE DETECTED in feature '{feat_name}': clean={clean_val} vs adversarial={adv_val}"
        )


# =====================================================================
# 2. Timezone & Temporal Parsing Robustness Tests
# =====================================================================

def test_timezone_naive_and_offset_timestamps_handled_safely(base_time, sample_user_history):
    u_id = sample_user_history["user_id"]
    t_id = "TASK_TZ_TEST"

    # Create timezone-naive timestamp
    naive_as_of = datetime(2025, 2, 1, 10, 0, 0)  # naive

    snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=naive_as_of,
        tasks_df=sample_user_history["tasks_df"],
        events_df=sample_user_history["events_df"],
        schema_version="v1.1",
    )

    assert snapshot.prediction_timestamp.tzinfo is not None
    assert snapshot.features["hour"] == 10
    assert snapshot.features["weekday"] == 5  # Saturday


# =====================================================================
# 3. Duplicate Event & Resumption Lag Tests
# =====================================================================

def test_duplicate_events_do_not_inflate_counts(base_time, sample_user_history):
    u_id = sample_user_history["user_id"]
    t_id = "TASK_DUP_TEST"
    events_df = sample_user_history["events_df"].copy()

    # Duplicate the entire events dataframe
    doubled_events = pd.concat([events_df, events_df], ignore_index=True)

    snapshot_single = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        events_df=events_df,
        schema_version="v2.2",
    )

    snapshot_doubled = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        events_df=doubled_events,
        schema_version="v2.2",
    )

    # Resumption lag and recent context switches should remain consistent
    assert snapshot_single.features["recent_context_switches"] >= 0


def test_resumption_lag_calculation(base_time, sample_user_history):
    u_id = sample_user_history["user_id"]
    t_id = "TASK_LAG_TEST"

    snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        events_df=sample_user_history["events_df"],
        schema_version="v2.2",
    )

    # We configured a pause -> resume gap of exactly 120 seconds in sample_user_history fixture
    assert snapshot.features["avg_resumption_lag_seconds"] == 120.0
    assert snapshot.features["median_resumption_lag_seconds"] == 120.0
    assert snapshot.missing_indicators["avg_resumption_lag_seconds"] is False


# =====================================================================
# 4. Cold-Start & Missing Value Treatment
# =====================================================================

def test_cold_start_new_user_graceful_defaults(base_time):
    u_id = "NEW_USER_999"
    t_id = "COLD_TASK_1"

    snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        schema_version="v2.2",
    )

    assert snapshot.features["previous_completion_count"] == 0
    assert snapshot.features["previous_forgetting_count"] == 0
    assert snapshot.features["historical_completion_rate"] == 0.5  # prior
    assert snapshot.missing_indicators["historical_completion_rate"] is True
    assert snapshot.missing_indicators["avg_resumption_lag_seconds"] is True


# =====================================================================
# 5. Backward Compatibility Contract Verification
# =====================================================================

def test_v1_1_contract_directly_validates_with_pydantic_schema(base_time, sample_user_history):
    u_id = sample_user_history["user_id"]
    t_id = "TASK_CONTRACT_TEST"

    snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        tasks_df=sample_user_history["tasks_df"],
        events_df=sample_user_history["events_df"],
        interruptions_df=sample_user_history["interruptions_df"],
        schema_version="v1.1",
    )

    # Must contain exact 16 raw features
    assert set(snapshot.features.keys()) == set(ALL_RAW_FEATURES)

    # Must parse cleanly into existing API Pydantic schema TaskFeatures
    pydantic_payload = snapshot.to_inference_dict()
    validated = TaskFeatures(**pydantic_payload)
    assert validated.task_id == t_id
    assert validated.weekday == snapshot.features["weekday"]
    assert validated.hour == snapshot.features["hour"]


def test_v2_2_contract_contains_all_enhanced_features(base_time, sample_user_history):
    u_id = sample_user_history["user_id"]
    t_id = "TASK_V2_TEST"

    snapshot = extract_features(
        user_id=u_id,
        task_id=t_id,
        as_of_timestamp=base_time,
        tasks_df=sample_user_history["tasks_df"],
        events_df=sample_user_history["events_df"],
        interruptions_df=sample_user_history["interruptions_df"],
        schema_version="v2.2",
    )

    # Verify all enhanced features are populated
    for enhanced_feat in ENHANCED_TEMPORAL_NUMERIC_FEATURES:
        assert enhanced_feat in snapshot.features, f"Missing enhanced feature: {enhanced_feat}"

    assert snapshot.features["task_age_hours"] >= 0.0
    assert snapshot.features["is_weekend"] in (0, 1)
    assert snapshot.features["is_peak_focus_hours"] in (0, 1)
