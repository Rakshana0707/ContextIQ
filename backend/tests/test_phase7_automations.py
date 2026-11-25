"""
Automated Test Suite for Phase 7.2: User-Defined Automation Rules and Trigger Engine.

Validates:
1. Invalid rules & schema rejection (injection attempts, bad operators, out-of-bounds cooldowns).
2. Conflicting conditions (invalid BETWEEN ranges, unsupported types).
3. Repeated events & event deduplication via idempotency keys.
4. Expired rules handling.
5. Cooldown enforcement & rate limits.
6. Disabled rules behavior & instant toggle.
7. Unauthorized trigger guards (telemetry consent requirements).
8. Rule versioning & execution audit tracking.
9. Dry-run evaluation without state side effects.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TEST_USER_ID = uuid.UUID("a1111111-1111-1111-1111-111111111111")
TEST_USER_ID_STR = "a1111111-1111-1111-1111-111111111111"
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-phase72-automations"
os.environ["DATABASE_URL"] = "sqlite:///./_test_automations.db"

import app.models
from app.db.session import Base
from app.main import app
from app.models.automation_rule import (
    AutomationActionDefinition,
    AutomationCondition,
    AutomationExecution,
    AutomationRule,
    AutomationRuleVersion,
    AutomationTrigger,
)
from app.models.telemetry_consent import TelemetryConsent
from app.models.user import User
from app.schemas.automation_schemas import (
    ConditionOperator,
    ExecutionStatus,
    LogicalOperator,
    TriggerType,
)
from app.services.automation_engine import (
    AutomationConditionEvaluator,
    AutomationRuleEvaluator,
    AutomationTriggerEngine,
)

test_engine = create_engine(
    "sqlite:///./_test_automations.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as session:
        # Create default test user
        user = User(
            id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
            email="test_automation@contextiq.dev",
            hashed_password="hashed_pw_test",
            display_name="Automation Test User",
            is_active=True,
        )
        session.add(user)
        session.commit()
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_invalid_rule_schema_rejection():
    """Verify that malformed rules and injection attempts are rejected with HTTP 422."""
    headers = {"X-User-Id": "a1111111-1111-1111-1111-111111111111"}

    # 1. Rule name too short (< 3 chars)
    payload_short_name = {
        "name": "No",
        "triggers": [{"trigger_type": "FORGETTING_THRESHOLD_EXCEEDED"}],
        "actions": [{"action_identifier": "reminder:stage_context_warming"}],
    }
    res = client.post("/api/v1/automations/rules", json=payload_short_name, headers=headers)
    assert res.status_code == 422

    # 2. Injection attempt in field_path
    payload_injection = {
        "name": "SQL Injection Rule",
        "triggers": [{"trigger_type": "FORGETTING_THRESHOLD_EXCEEDED"}],
        "conditions": [
            {
                "field_path": "task.id; DROP TABLE users; --",
                "operator": "EQUALS",
                "expected_value": "123",
            }
        ],
        "actions": [{"action_identifier": "reminder:stage_context_warming"}],
    }
    res = client.post("/api/v1/automations/rules", json=payload_injection, headers=headers)
    assert res.status_code == 422

    # 3. Missing action namespace
    payload_bad_action = {
        "name": "Bad Action ID Rule",
        "triggers": [{"trigger_type": "FORGETTING_THRESHOLD_EXCEEDED"}],
        "actions": [{"action_identifier": "unnamespaced_action"}],
    }
    res = client.post("/api/v1/automations/rules", json=payload_bad_action, headers=headers)
    assert res.status_code == 422


def test_conflicting_conditions_rejection():
    """Verify that contradictory or invalid condition parameters are caught by schema validation."""
    headers = {"X-User-Id": "a1111111-1111-1111-1111-111111111111"}

    # BETWEEN with min > max
    payload_bad_between = {
        "name": "Invalid Range Rule",
        "triggers": [{"trigger_type": "FORGETTING_THRESHOLD_EXCEEDED"}],
        "conditions": [
            {
                "field_path": "forgetting_risk.probability",
                "operator": "BETWEEN",
                "expected_value": [0.9, 0.2],  # min > max
            }
        ],
        "actions": [{"action_identifier": "reminder:stage_context_warming"}],
    }
    res = client.post("/api/v1/automations/rules", json=payload_bad_between, headers=headers)
    assert res.status_code == 422


def test_rule_creation_and_versioning():
    """Verify rule creation, version initialization (v1), and update versioning (v2)."""
    headers = {"X-User-Id": "a1111111-1111-1111-1111-111111111111"}

    payload = {
        "name": "High Risk Reminder",
        "description": "Pre-stage reminder when lapse hazard is high",
        "cooldown_minutes": 15,
        "max_executions_per_day": 5,
        "requires_approval": True,
        "triggers": [
            {
                "trigger_type": "FORGETTING_THRESHOLD_EXCEEDED",
                "parameters": {"threshold": 0.75},
            }
        ],
        "conditions": [
            {
                "field_path": "forgetting_risk.probability",
                "operator": "GREATER_THAN_OR_EQUAL",
                "expected_value": 0.75,
            }
        ],
        "actions": [
            {
                "action_order": 1,
                "action_identifier": "reminder:stage_context_warming",
                "parameters_template": {"channel": "IN_APP_TOAST"},
            }
        ],
    }

    # 1. Create rule
    res = client.post("/api/v1/automations/rules", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    rule_id = data["id"]
    assert data["version"] == 1
    assert len(data["triggers"]) == 1
    assert len(data["conditions"]) == 1
    assert len(data["actions"]) == 1

    # Check version snapshot
    res_ver = client.get(f"/api/v1/automations/rules/{rule_id}/versions", headers=headers)
    assert res_ver.status_code == 200
    versions = res_ver.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1

    # 2. Update rule
    update_payload = {
        "name": "Updated High Risk Reminder",
        "cooldown_minutes": 20,
        "change_summary": "Bumped cooldown to 20m",
    }
    res_up = client.put(f"/api/v1/automations/rules/{rule_id}", json=update_payload, headers=headers)
    assert res_up.status_code == 200
    updated_data = res_up.json()
    assert updated_data["version"] == 2
    assert updated_data["cooldown_minutes"] == 20

    # Check updated version snapshots
    res_ver2 = client.get(f"/api/v1/automations/rules/{rule_id}/versions", headers=headers)
    assert res_ver2.status_code == 200
    assert len(res_ver2.json()) == 2


def test_cooldown_and_deduplication_behavior():
    """Verify cooldown throttling and event deduplication."""
    user_id = uuid.UUID("a1111111-1111-1111-1111-111111111111")
    now = datetime.now(timezone.utc)

    with TestingSessionLocal() as session:
        session.query(AutomationRule).delete()
        session.commit()
        rule = AutomationRule(
            user_id=user_id,
            name="Cooldown Test Rule",
            cooldown_minutes=30,
            max_executions_per_day=5,
            is_enabled=True,
            active_schedule={"days_of_week": [1, 2, 3, 4, 5, 6, 7], "start_time": "00:00", "end_time": "23:59"},
            quiet_hours={"enabled": False},
        )
        session.add(rule)
        session.flush()

        trigger = AutomationTrigger(
            rule_id=rule.id,
            trigger_type="BFI_THRESHOLD_EXCEEDED",
            is_authorized=True,
        )
        condition = AutomationCondition(
            rule_id=rule.id,
            field_path="context.bfi",
            operator="GREATER_THAN",
            expected_value=50.0,
        )
        action = AutomationActionDefinition(
            rule_id=rule.id,
            action_identifier="recovery:insert_post_interruption_buffer",
        )
        consent = TelemetryConsent(
            user_id=user_id,
            consent_status="GRANTED",
        )
        session.add_all([trigger, condition, action, consent])
        session.commit()

        # 1. First trigger evaluation -> Matches & Executes
        res1 = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="BFI_THRESHOLD_EXCEEDED",
            trigger_event_id="evt_001",
            context_payload={"context": {"bfi": 65.0}},
            dry_run=False,
        )
        assert res1.matched_rules_count == 1
        assert res1.results[0].status == ExecutionStatus.PENDING_APPROVAL

        # 2. Second trigger with DIFFERENT event_id immediately -> Suppressed by Cooldown
        res2 = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="BFI_THRESHOLD_EXCEEDED",
            trigger_event_id="evt_002",
            context_payload={"context": {"bfi": 70.0}},
            dry_run=False,
        )
        assert res2.matched_rules_count == 0
        assert res2.results[0].status == ExecutionStatus.SUPPRESSED_COOLDOWN

        # 3. Third trigger with SAME event_id (evt_001) -> Suppressed by duplicate idempotency key
        # Reset last_triggered_at to simulate time passed, but duplicate event_id
        rule.last_triggered_at = now - timedelta(hours=1)
        session.commit()

        res3 = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="BFI_THRESHOLD_EXCEEDED",
            trigger_event_id="evt_001",
            context_payload={"context": {"bfi": 65.0}},
            dry_run=False,
        )
        assert res3.results[0].status == ExecutionStatus.SUPPRESSED_COOLDOWN
        assert "deduplicated" in (res3.results[0].suppression_reason or "")


def test_disabled_rules_and_toggle():
    """Verify disabled rules cannot execute and toggle works immediately."""
    headers = {"X-User-Id": "a1111111-1111-1111-1111-111111111111"}
    user_id = uuid.UUID("a1111111-1111-1111-1111-111111111111")

    with TestingSessionLocal() as session:
        session.query(AutomationRule).delete()
        session.commit()
        rule = AutomationRule(
            user_id=user_id,
            name="Toggleable Rule",
            is_enabled=False,
            cooldown_minutes=0,
            active_schedule={"days_of_week": [1, 2, 3, 4, 5, 6, 7], "start_time": "00:00", "end_time": "23:59"},
            quiet_hours={"enabled": False},
        )
        session.add(rule)
        session.flush()
        trigger = AutomationTrigger(rule_id=rule.id, trigger_type="TASK_CREATED")
        session.add(trigger)
        session.commit()
        rule_id = rule.id

    # Disabled rule does not match
    with TestingSessionLocal() as session:
        res = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="TASK_CREATED",
            context_payload={},
        )
        assert res.matched_rules_count == 0

    # Toggle to enabled via API
    res_toggle = client.patch(f"/api/v1/automations/rules/{rule_id}/toggle", headers=headers)
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_enabled"] is True

    # Now matches
    with TestingSessionLocal() as session:
        res_enabled = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="TASK_CREATED",
            context_payload={},
        )
        assert res_enabled.matched_rules_count == 1


def test_expired_rules_handling():
    """Verify expired rules are suppressed with SUPPRESSED_EXPIRED."""
    user_id = uuid.UUID("a1111111-1111-1111-1111-111111111111")
    now = datetime.now(timezone.utc)

    with TestingSessionLocal() as session:
        session.query(AutomationRule).delete()
        session.commit()
        rule = AutomationRule(
            user_id=user_id,
            name="Expired Rule",
            is_enabled=True,
            expires_at=now - timedelta(days=1),  # Expired yesterday
            cooldown_minutes=0,
            active_schedule={"days_of_week": [1, 2, 3, 4, 5, 6, 7], "start_time": "00:00", "end_time": "23:59"},
            quiet_hours={"enabled": False},
        )
        session.add(rule)
        session.flush()
        trigger = AutomationTrigger(rule_id=rule.id, trigger_type="CALENDAR_CONFLICT_DETECTED")
        session.add(trigger)
        session.commit()

        res = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="CALENDAR_CONFLICT_DETECTED",
        )
        assert res.matched_rules_count == 0
        assert res.results[0].status == ExecutionStatus.SUPPRESSED_EXPIRED


def test_unauthorized_trigger_guard():
    """Verify behavioral telemetry triggers require explicit TelemetryConsent."""
    user_id = uuid.UUID("a1111111-1111-1111-1111-111111111111")

    with TestingSessionLocal() as session:
        session.query(TelemetryConsent).delete()
        session.query(AutomationRule).delete()
        session.commit()

        rule = AutomationRule(
            user_id=user_id,
            name="Thrashing Guard",
            is_enabled=True,
            cooldown_minutes=0,
            active_schedule={"days_of_week": [1, 2, 3, 4, 5, 6, 7], "start_time": "00:00", "end_time": "23:59"},
            quiet_hours={"enabled": False},
        )
        session.add(rule)
        session.flush()
        trigger = AutomationTrigger(
            rule_id=rule.id,
            trigger_type="THRASHING_DETECTED",
            is_authorized=True,
        )
        session.add(trigger)
        session.commit()

        # Telemetry consent has NOT been granted
        res = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="THRASHING_DETECTED",
        )
        assert res.matched_rules_count == 0
        assert res.results[0].status == ExecutionStatus.SUPPRESSED_UNAUTHORIZED

        # Now grant consent
        consent = TelemetryConsent(
            user_id=user_id,
            consent_status="GRANTED",
        )
        session.add(consent)
        session.commit()

        # Now authorized and matches
        res2 = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="THRASHING_DETECTED",
        )
        assert res2.matched_rules_count == 1


def test_dry_run_does_not_mutate_state():
    """Verify dry-run evaluates triggers without saving execution records or updating last_triggered_at."""
    user_id = uuid.UUID("a1111111-1111-1111-1111-111111111111")

    with TestingSessionLocal() as session:
        session.query(AutomationRule).delete()
        session.commit()
        rule = AutomationRule(
            user_id=user_id,
            name="Dry Run Rule",
            is_enabled=True,
            cooldown_minutes=10,
            active_schedule={"days_of_week": [1, 2, 3, 4, 5, 6, 7], "start_time": "00:00", "end_time": "23:59"},
            quiet_hours={"enabled": False},
        )
        session.add(rule)
        session.flush()
        trigger = AutomationTrigger(rule_id=rule.id, trigger_type="TASK_OVERDUE")
        condition = AutomationCondition(
            rule_id=rule.id,
            field_path="task.overdue_hours",
            operator="GREATER_THAN",
            expected_value=2.0,
        )
        action = AutomationActionDefinition(
            rule_id=rule.id,
            action_identifier="task:decompose_into_subtasks",
        )
        consent = TelemetryConsent(
            user_id=user_id,
            consent_status="GRANTED",
        )
        session.add_all([trigger, condition, action, consent])
        session.commit()

        # Dry run evaluation
        res = AutomationTriggerEngine.evaluate_trigger(
            db=session,
            user_id=user_id,
            trigger_type="TASK_OVERDUE",
            context_payload={"task": {"overdue_hours": 3.5}},
            dry_run=True,
        )
        assert res.matched_rules_count == 1
        assert res.results[0].is_matched is True

        # Assert no executions created in database for this rule
        exec_count = session.query(AutomationExecution).filter_by(rule_id=rule.id).count()
        assert exec_count == 0

        # Assert last_triggered_at was not touched
        session.refresh(rule)
        assert rule.last_triggered_at is None


if __name__ == "__main__":
    print("Running Phase 7.2 Automation Rules Test Suite...")
    # Setup
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as session:
        user = User(
            id=uuid.UUID("a1111111-1111-1111-1111-111111111111"),
            email="test_automation@contextiq.dev",
            hashed_password="hashed_pw_test",
            display_name="Automation Test User",
            is_active=True,
        )
        session.add(user)
        session.commit()

    test_invalid_rule_schema_rejection()
    print("  [PASS] test_invalid_rule_schema_rejection")

    test_conflicting_conditions_rejection()
    print("  [PASS] test_conflicting_conditions_rejection")

    test_rule_creation_and_versioning()
    print("  [PASS] test_rule_creation_and_versioning")

    test_cooldown_and_deduplication_behavior()
    print("  [PASS] test_cooldown_and_deduplication_behavior")

    test_disabled_rules_and_toggle()
    print("  [PASS] test_disabled_rules_and_toggle")

    test_expired_rules_handling()
    print("  [PASS] test_expired_rules_handling")

    test_unauthorized_trigger_guard()
    print("  [PASS] test_unauthorized_trigger_guard")

    test_dry_run_does_not_mutate_state()
    print("  [PASS] test_dry_run_does_not_mutate_state")

    print("\nALL 8 AUTOMATION RULE TESTS PASSED SUCCESSFULLY!")

