"""
test_label_system.py

Unit and integration tests for ContextIQ's Formal Target Labeling System
and Automated Label Quality Validator (Phase 2.1).
"""

from datetime import datetime, timedelta, timezone
import pytest
import pandas as pd

from ml.data.label_generator import (
    OutcomeType,
    LabelingConfig,
    generate_task_label,
    generate_labels_for_dataframe,
    compute_grace_period_hours,
)
from ml.data.label_validator import LabelValidator


@pytest.fixture
def config():
    return LabelingConfig(
        grace_period_hours=4.0,
        grace_period_ratio=0.10,
        max_grace_period_hours=24.0,
        abandon_inactivity_hours=48.0,
        dormant_inactivity_days=14.0,
    )


@pytest.fixture
def base_time():
    return datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc)


# =====================================================================
# 1. Individual Outcome Classification Rules
# =====================================================================

def test_completed_on_time_before_deadline(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=8)
    completed_at = base_time + timedelta(hours=5)
    as_of = base_time + timedelta(hours=24)

    task = {
        "id": "T001",
        "created_at": created_at,
        "deadline_at": deadline_at,
        "completed_at": completed_at,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.COMPLETED_ON_TIME
    assert result.will_forget == 0
    assert result.is_valid_training_sample is True
    assert result.labeling_timestamp == completed_at


def test_completed_on_time_during_grace_period(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=8)
    # Deadline + 2h is inside the 4h grace period
    completed_at = deadline_at + timedelta(hours=2)
    as_of = base_time + timedelta(hours=24)

    task = {
        "id": "T002",
        "created_at": created_at,
        "deadline_at": deadline_at,
        "completed_at": completed_at,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.COMPLETED_ON_TIME
    assert result.will_forget == 0
    assert result.is_valid_training_sample is True


def test_completed_late_after_grace_period(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=8)
    # Grace is 4h. Completed 6h after deadline -> tardy
    completed_at = deadline_at + timedelta(hours=6)
    as_of = base_time + timedelta(hours=48)

    task = {
        "id": "T003",
        "created_at": created_at,
        "deadline_at": deadline_at,
        "completed_at": completed_at,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.COMPLETED_LATE
    assert result.will_forget == 0  # Not forgotten, but tardy
    assert result.is_valid_training_sample is True
    assert result.metadata["completion_delay_hours"] == 6.0


def test_explicitly_forgotten_unstarted_past_deadline(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=8)
    # as_of is 24h later, grace period expired, zero work was done
    as_of = base_time + timedelta(hours=24)

    task = {
        "id": "T004",
        "created_at": created_at,
        "deadline_at": deadline_at,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.EXPLICITLY_FORGOTTEN
    assert result.will_forget == 1
    assert result.is_valid_training_sample is True


def test_abandoned_task_started_then_idle(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=10)
    start_time = base_time + timedelta(hours=2)
    # As of is past deadline+grace, but user started the task and then dropped it
    as_of = base_time + timedelta(hours=30)

    task = {
        "id": "T005",
        "created_at": created_at,
        "deadline_at": deadline_at,
        "started_at": start_time,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.ABANDONED
    assert result.will_forget == 1
    assert result.is_valid_training_sample is True


def test_intentionally_postponed_task(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=8)
    as_of = base_time + timedelta(hours=24)

    events = [
        {"event_type": "created", "timestamp": created_at},
        {"event_type": "postponed", "timestamp": base_time + timedelta(hours=6)},
    ]
    task = {
        "id": "T006",
        "created_at": created_at,
        "deadline_at": deadline_at,
    }
    result = generate_task_label(task, events=events, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.POSTPONED
    assert result.will_forget == 0  # Healthy deferral
    assert result.is_valid_training_sample is True


def test_overdue_task_in_grace_window(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=8)
    # as_of is 2h past deadline, but grace period is 4h -> in-flight
    as_of = deadline_at + timedelta(hours=2)

    task = {
        "id": "T007",
        "created_at": created_at,
        "deadline_at": deadline_at,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.OVERDUE
    assert result.will_forget is None
    assert result.is_valid_training_sample is False
    assert result.censoring_reason is not None


def test_dormant_unscheduled_task(base_time, config):
    created_at = base_time
    # 20 days later, no deadline, zero activity
    as_of = base_time + timedelta(days=20)

    task = {
        "id": "T008",
        "created_at": created_at,
        "deadline_at": None,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.DORMANT
    assert result.will_forget is None
    assert result.is_valid_training_sample is False


def test_right_censored_future_task(base_time, config):
    created_at = base_time
    deadline_at = base_time + timedelta(hours=48)
    # as_of is 12h after creation, deadline still far in future
    as_of = base_time + timedelta(hours=12)

    task = {
        "id": "T009",
        "created_at": created_at,
        "deadline_at": deadline_at,
    }
    result = generate_task_label(task, as_of=as_of, config=config)

    assert result.outcome_type == OutcomeType.CENSORED
    assert result.will_forget is None
    assert result.is_valid_training_sample is False
    assert "Deadline has not yet arrived" in result.censoring_reason


# =====================================================================
# 2. Temporal Non-Leakage Verification
# =====================================================================

def test_future_events_cannot_influence_historical_label(base_time, config):
    """
    CRITICAL LEAKAGE TEST:
    A task is evaluated at as_of = base_time + 10h (when it is still in-progress/censored).
    A future event (e.g., completed at base_time + 30h) must be invisible to the labeler.
    """
    created_at = base_time
    deadline_at = base_time + timedelta(hours=24)
    cutoff_time = base_time + timedelta(hours=10)
    future_completion = base_time + timedelta(hours=20)

    events = [
        {"event_type": "created", "timestamp": created_at},
        {"event_type": "started", "timestamp": base_time + timedelta(hours=2)},
        # Future event after cutoff:
        {"event_type": "completed", "timestamp": future_completion},
    ]

    task = {
        "id": "T_LEAK_01",
        "created_at": created_at,
        "deadline_at": deadline_at,
    }

    # Label evaluated strictly at cutoff_time
    result = generate_task_label(task, events=events, as_of=cutoff_time, config=config)

    # Must be CENSORED as of cutoff_time, ignoring the future completion!
    assert result.outcome_type == OutcomeType.CENSORED
    assert result.will_forget is None
    assert result.is_valid_training_sample is False

    # But if evaluated after future completion, it recognizes on-time completion
    result_later = generate_task_label(task, events=events, as_of=future_completion + timedelta(hours=1), config=config)
    assert result_later.outcome_type == OutcomeType.COMPLETED_ON_TIME
    assert result_later.will_forget == 0


# =====================================================================
# 3. Label Quality Validator Suite Tests
# =====================================================================

def test_validator_catches_contradictory_events(base_time):
    validator = LabelValidator()
    created_at = base_time
    tasks_df = pd.DataFrame([{"id": "T_BAD_1", "created_at": created_at, "will_forget": 0}])
    events_df = pd.DataFrame([
        {"task_id": "T_BAD_1", "event_type": "completed", "timestamp": created_at + timedelta(hours=2)},
        {"task_id": "T_BAD_1", "event_type": "forgotten", "timestamp": created_at + timedelta(hours=4)},
    ])

    summary = validator.validate(tasks_df, events_df=events_df, as_of=base_time + timedelta(days=1))
    assert "CONTRADICTORY_EVENTS" in summary.anomalies_by_check
    assert summary.anomalies_by_check["CONTRADICTORY_EVENTS"] >= 1


def test_validator_catches_impossible_timestamps(base_time):
    validator = LabelValidator()
    created_at = base_time
    tasks_df = pd.DataFrame([{"id": "T_BAD_2", "created_at": created_at, "will_forget": 0}])
    # Event before creation
    events_df = pd.DataFrame([
        {"task_id": "T_BAD_2", "event_type": "started", "timestamp": created_at - timedelta(hours=2)},
    ])

    summary = validator.validate(tasks_df, events_df=events_df, as_of=base_time + timedelta(days=1))
    assert "IMPOSSIBLE_TIMESTAMPS" in summary.anomalies_by_check


def test_validator_catches_duplicate_events(base_time):
    validator = LabelValidator()
    created_at = base_time
    tasks_df = pd.DataFrame([{"id": "T_BAD_3", "created_at": created_at, "will_forget": 0}])
    ev_time = created_at + timedelta(hours=1)
    events_df = pd.DataFrame([
        {"task_id": "T_BAD_3", "event_type": "started", "timestamp": ev_time},
        {"task_id": "T_BAD_3", "event_type": "started", "timestamp": ev_time},
    ])

    summary = validator.validate(tasks_df, events_df=events_df, as_of=base_time + timedelta(days=1))
    assert "DUPLICATE_EVENTS" in summary.anomalies_by_check


def test_validator_catches_tardy_mislabeled_as_forgotten(base_time):
    validator = LabelValidator()
    created_at = base_time
    deadline = base_time + timedelta(hours=4)
    comp_t = base_time + timedelta(hours=10)

    tasks_df = pd.DataFrame([{
        "id": "T_BAD_4",
        "created_at": created_at,
        "deadline_at": deadline,
        "completed_at": comp_t,
        "will_forget": 1,  # BUG: completed task labeled as forgotten!
    }])

    summary = validator.validate(tasks_df, as_of=base_time + timedelta(days=1))
    assert "TARDY_MISLABELED_FORGOTTEN" in summary.anomalies_by_check


def test_validator_catches_postponed_mislabeled_as_forgotten(base_time):
    validator = LabelValidator()
    created_at = base_time
    tasks_df = pd.DataFrame([{
        "id": "T_BAD_5",
        "created_at": created_at,
        "will_forget": 1,  # BUG: postponed labeled as forgotten!
        "is_postponed": True,
    }])

    summary = validator.validate(tasks_df, as_of=base_time + timedelta(days=1))
    assert "POSTPONEMENT_MISLABELED_FORGOTTEN" in summary.anomalies_by_check


def test_validator_clean_dataset_passes_without_anomalies(base_time, config):
    """Generates clean labels via label_generator, then verifies validator passes with 0 anomalies."""
    created_at = base_time
    clean_tasks = [
        {"id": "CLEAN_1", "created_at": created_at, "deadline_at": created_at + timedelta(hours=6), "completed_at": created_at + timedelta(hours=3)},
        {"id": "CLEAN_2", "created_at": created_at, "deadline_at": created_at + timedelta(hours=4), "completed_at": created_at + timedelta(hours=12)},
        {"id": "CLEAN_3", "created_at": created_at, "deadline_at": created_at + timedelta(hours=4), "started_at": created_at + timedelta(hours=1)},
        {"id": "CLEAN_4", "created_at": created_at, "deadline_at": created_at + timedelta(hours=4)},
    ]
    tasks_df = pd.DataFrame(clean_tasks)
    as_of = base_time + timedelta(days=2)

    labeled_df = generate_labels_for_dataframe(tasks_df, as_of=as_of, config=config)

    validator = LabelValidator()
    summary = validator.validate(tasks_df, labeled_df=labeled_df, as_of=as_of)

    assert len(summary.anomalies) == 0
    assert summary.valid_training_samples == 4
    assert summary.outcome_distribution[OutcomeType.COMPLETED_ON_TIME.value] == 1
    assert summary.outcome_distribution[OutcomeType.COMPLETED_LATE.value] == 1
    assert summary.outcome_distribution[OutcomeType.ABANDONED.value] == 1
    assert summary.outcome_distribution[OutcomeType.EXPLICITLY_FORGOTTEN.value] == 1
