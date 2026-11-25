"""Unit and integration test suite for calendar-aware intelligent task scheduling engine."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend directory and project root to sys.path
backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

# Teach SQLite how to compile Postgres JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-master-secret-for-phase5-encryption"
os.environ["DATABASE_URL"] = "sqlite:///./_test_integrations.db"

from app.db.session import Base, engine
from app.main import app
from app.models.calendar_integration import CalendarCredential, CalendarIntegration, CalendarSyncState
from app.models.enums import TaskPriority, TaskStatus
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.focus_window import UserFocusWindow
from app.models.schedule_proposal import ScheduleProposal
from app.models.task import Task
from app.models.user import User
from app.schemas.scheduling import (
    ScheduleApprovalRequest,
    ScheduleGenerateRequest,
    ScheduleModifySlotRequest,
    ScheduleRejectRequest,
)
from app.scheduling.availability_engine import AvailabilityEngine
from app.scheduling.task_scheduler import TaskScheduler
from app.services import scheduling_service
from app.services.integration_service import get_token_manager
from integrations.app.core.token_manager import TokenManager
from integrations.app.providers.google.google_calendar_provider import GoogleCalendarProvider
from integrations.app.schemas.integration_schemas import (
    CalendarEventDTO,
    ConnectionStatus,
    EventStatus,
    EventTransparency,
    OAuthTokenBundle,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user():
    uid = uuid.uuid4()
    with Session(engine) as session:
        u = User(
            id=uid,
            email=f"scheduser_{uid.hex[:6]}@example.com",
            display_name="Scheduling User",
        )
        session.add(u)
        session.commit()
    return uid


@pytest.fixture
def user_with_calendar(test_user):
    token_mgr = get_token_manager()
    bundle = OAuthTokenBundle(
        access_token="ya29.test_sched_access_token",
        refresh_token="1//refresh_sched_tok",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        scope=["https://www.googleapis.com/auth/calendar.events"],
    )
    enc_access, enc_refresh = token_mgr.encrypt_credentials(bundle, user_id=test_user, provider="google_calendar")

    with Session(engine) as session:
        integration = CalendarIntegration(
            user_id=test_user,
            provider="google_calendar",
            provider_account_id="google-sub-sched",
            provider_email="sched.user@gmail.com",
            connection_status=ConnectionStatus.CONNECTED.value,
            granted_scopes=bundle.scope,
            is_active=True,
        )
        session.add(integration)
        session.flush()

        credential = CalendarCredential(
            integration_id=integration.id,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            token_type="Bearer",
            expiration_timestamp=bundle.expires_at,
            credential_version=1,
        )
        session.add(credential)

        # Add a personal focus window: 09:30 to 11:30 with 85% quality score
        now_dt = datetime.now(timezone.utc)
        focus_win = UserFocusWindow(
            user_id=test_user,
            task_category="deep_work",
            start_time=time(9, 30),
            end_time=time(11, 30),
            duration_minutes=120,
            quality_score=85.0,
            confidence_score=0.92,
            observation_count=25,
            is_active=True,
        )
        session.add(focus_win)
        session.commit()
        return integration.id, test_user


# ============================================================================
# 1. TASK 2: AVAILABILITY ENGINE CALCULATIONS
# ============================================================================

def test_availability_empty_calendar_clamps_to_working_hours(test_user):
    """An empty calendar must never imply 24h availability; only working hours minus lunch."""
    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        start_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        # Ensure start_date is a weekday
        if start_date.weekday() >= 5:
            start_date += timedelta(days=2)

        resp = AvailabilityEngine.calculate_availability(
            db=session,
            user_id=test_user,
            start_date=start_date,
            horizon_days=1,
            working_hour_start=9,
            working_hour_end=17,
            enforce_lunch_break=True,
            lunch_start_hour=12,
            lunch_duration_minutes=60,
        )

        assert resp.total_available_minutes > 0
        # 8h working hours (09:00 - 17:00) minus 1h lunch = 7h (420 mins)
        assert resp.total_available_minutes == 420
        assert len(resp.available_windows) == 2  # Morning (09:00-12:00) & Afternoon (13:00-17:00)
        assert any(b.source == "lunch_break" for b in resp.busy_blocks)


def test_availability_subtracts_calendar_events_and_recovery_buffer(user_with_calendar):
    integration_id, user_id = user_with_calendar

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        start_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if start_date.weekday() >= 5:
            start_date += timedelta(days=2)

        # Insert a 10:00 - 11:00 team meeting
        m_start = start_date.replace(hour=10, minute=0)
        m_end = start_date.replace(hour=11, minute=0)
        meeting = ExternalCalendarEvent(
            user_id=user_id,
            integration_id=integration_id,
            calendar_id="primary",
            external_event_id="meeting-avail-1",
            title="Team Architecture Review",
            start_time=m_start,
            end_time=m_end,
            transparency="OPAQUE",
            status="CONFIRMED",
        )
        session.add(meeting)
        session.commit()

        # Calculate availability with 15-min recovery buffer
        resp = AvailabilityEngine.calculate_availability(
            db=session,
            user_id=user_id,
            start_date=start_date,
            horizon_days=1,
            working_hour_start=9,
            working_hour_end=17,
            enforce_lunch_break=True,
            lunch_start_hour=12,
            lunch_duration_minutes=60,
            recovery_buffer_minutes=15,
        )

        # Busy blocks must include Meeting + Post-Meeting Recovery Buffer + Lunch
        assert any(b.title == "Team Architecture Review" for b in resp.busy_blocks)
        assert any(b.is_recovery_buffer is True and "15m" in b.title for b in resp.busy_blocks)
        # 420 min - 60 min (meeting) - 15 min (recovery) = 345 mins
        assert resp.total_available_minutes == 345


def test_availability_fully_occupied_calendar(user_with_calendar):
    """When a day is completely booked with meetings, availability drops to 0."""
    integration_id, user_id = user_with_calendar

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        start_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=2)
        if start_date.weekday() >= 5:
            start_date += timedelta(days=2)

        # Full day meeting 09:00 - 17:00
        full_meeting = ExternalCalendarEvent(
            user_id=user_id,
            integration_id=integration_id,
            calendar_id="primary",
            external_event_id="meeting-full-day",
            title="All-Day Offsite Workshop",
            start_time=start_date.replace(hour=9, minute=0),
            end_time=start_date.replace(hour=17, minute=0),
            transparency="OPAQUE",
            status="CONFIRMED",
        )
        session.add(full_meeting)
        session.commit()

        resp = AvailabilityEngine.calculate_availability(
            db=session,
            user_id=user_id,
            start_date=start_date,
            horizon_days=1,
            working_hour_start=9,
            working_hour_end=17,
        )
        assert resp.total_available_minutes == 0
        assert len(resp.available_windows) == 0


# ============================================================================
# 2. TASK 3, 4, 5 & 6: SCHEDULING ALGORITHM & EXPLAINABILITY
# ============================================================================

def test_task_scheduling_prioritizes_urgent_and_deep_work(user_with_calendar):
    integration_id, user_id = user_with_calendar
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if base_date.weekday() >= 5:
        base_date += timedelta(days=2)

    with Session(engine) as session:
        # Task 1: Deep work task
        t_deep = Task(
            user_id=user_id,
            title="Refactor Core ML Engine",
            context_tag="programming",
            priority=TaskPriority.HIGH,
            estimated_minutes=60,
            status=TaskStatus.PENDING,
        )
        # Task 2: Urgent chore with imminent deadline
        t_urgent = Task(
            user_id=user_id,
            title="Submit Quarterly Financial Report",
            priority=TaskPriority.URGENT,
            estimated_minutes=30,
            due_at=base_date + timedelta(hours=4),  # Due at 13:00
            status=TaskStatus.PENDING,
        )
        session.add_all([t_deep, t_urgent])
        session.commit()

        req = ScheduleGenerateRequest(
            start_date=base_date,
            horizon_days=1,
            working_hour_start=9,
            working_hour_end=17,
            task_ids=[t_deep.id, t_urgent.id],
        )

        proposal = TaskScheduler.generate_schedule(db=session, user_id=user_id, request=req)

        assert proposal.status == "DRAFT"
        assert len(proposal.scheduled_items) == 2
        assert len(proposal.unscheduled_items) == 0

        # Urgent task scheduled before deadline
        urgent_slot = next(s for s in proposal.scheduled_items if s.task_id == t_urgent.id)
        assert urgent_slot.end_time <= base_date + timedelta(hours=4)

        # Deep work task explanation verification (Task 6)
        deep_slot = next(s for s in proposal.scheduled_items if s.task_id == t_deep.id)
        assert deep_slot.is_deep_work is True
        assert deep_slot.explanation.primary_rationale is not None
        assert len(deep_slot.explanation.behavioral_drivers) >= 2
        assert len(deep_slot.explanation.calendar_constraints) >= 2
        assert deep_slot.explanation.confidence_score >= 0.70


def test_task_scheduling_respects_parent_dependency(user_with_calendar):
    """Child task must be scheduled strictly after parent task completion."""
    integration_id, user_id = user_with_calendar
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if base_date.weekday() >= 5:
        base_date += timedelta(days=2)

    with Session(engine) as session:
        t_parent = Task(
            user_id=user_id,
            title="Draft Product Specifications",
            priority=TaskPriority.HIGH,
            estimated_minutes=45,
            status=TaskStatus.PENDING,
        )
        session.add(t_parent)
        session.flush()

        t_child = Task(
            user_id=user_id,
            title="Review Product Specifications with Engineering",
            priority=TaskPriority.HIGH,
            estimated_minutes=30,
            parent_task_id=t_parent.id,
            status=TaskStatus.PENDING,
        )
        session.add(t_child)
        session.commit()

        req = ScheduleGenerateRequest(
            start_date=base_date,
            horizon_days=1,
            task_ids=[t_parent.id, t_child.id],
        )
        proposal = TaskScheduler.generate_schedule(db=session, user_id=user_id, request=req)

        parent_slot = next(s for s in proposal.scheduled_items if s.task_id == t_parent.id)
        child_slot = next(s for s in proposal.scheduled_items if s.task_id == t_child.id)

        # Child starts at or after parent ends
        assert child_slot.start_time >= parent_slot.end_time


# ============================================================================
# 3. TASK 7 & 8: USER APPROVAL WORKFLOW & CALENDAR WRITING
# ============================================================================

def test_schedule_approval_commits_idempotently(user_with_calendar):
    integration_id, user_id = user_with_calendar
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if base_date.weekday() >= 5:
        base_date += timedelta(days=2)

    with Session(engine) as session:
        task = Task(
            user_id=user_id,
            title="Prepare Technical Board Presentation",
            priority=TaskPriority.URGENT,
            estimated_minutes=60,
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()

        # 1. Generate Proposal Draft
        req = ScheduleGenerateRequest(
            start_date=base_date,
            horizon_days=1,
            task_ids=[task.id],
        )
        proposal = scheduling_service.generate_schedule(db=session, user_id=user_id, request=req)
        assert proposal.status == "DRAFT"

        # Mock Google Calendar API event creation
        mock_created = CalendarEventDTO(
            event_id="goog-sched-focus-100",
            calendar_id="primary",
            provider="google_calendar",
            title=f"Focus: {task.title}",
            start_time=proposal.scheduled_items[0].start_time,
            end_time=proposal.scheduled_items[0].end_time,
        )

        with patch.object(GoogleCalendarProvider, "create_event", return_value=mock_created) as mock_create:
            # 2. Approve Schedule
            approval_req = ScheduleApprovalRequest(
                schedule_id=proposal.id,
                target_provider="google_calendar",
            )
            resp = scheduling_service.approve_schedule(db=session, user_id=user_id, request=approval_req)
            assert resp.success is True
            assert resp.events_created == 1
            assert resp.status == "COMMITTED"
            mock_create.assert_called_once()

            # Verify saved in external_calendar_events with is_contextiq_managed=True
            saved_evt = session.scalars(
                select(ExternalCalendarEvent).where(
                    ExternalCalendarEvent.linked_task_id == task.id,
                    ExternalCalendarEvent.external_event_id == "goog-sched-focus-100",
                )
            ).first()
            assert saved_evt is not None
            assert saved_evt.is_contextiq_managed is True

            # 3. Test Idempotency: re-approving same slot does not create duplicates
            resp_dup = scheduling_service.approve_schedule(db=session, user_id=user_id, request=approval_req)
            assert resp_dup.events_created == 1
            # create_event call count did not increase
            assert mock_create.call_count == 1


def test_schedule_rejection_leaves_calendar_untouched(user_with_calendar):
    integration_id, user_id = user_with_calendar
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if base_date.weekday() >= 5:
        base_date += timedelta(days=2)

    with Session(engine) as session:
        task = Task(
            user_id=user_id,
            title="Task for Rejected Proposal",
            priority=TaskPriority.LOW,
            estimated_minutes=30,
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()

        req = ScheduleGenerateRequest(start_date=base_date, horizon_days=1, task_ids=[task.id])
        proposal = scheduling_service.generate_schedule(db=session, user_id=user_id, request=req)

        # Reject proposal
        success = scheduling_service.reject_schedule(
            db=session, user_id=user_id, schedule_id=proposal.id, reason="User prefers manual scheduling"
        )
        assert success is True

        # Check DB status is REJECTED
        reloaded = session.scalars(select(ScheduleProposal).where(ScheduleProposal.id == proposal.id)).first()
        assert reloaded.status == "REJECTED"

        # Attempting to approve a rejected proposal must fail
        with pytest.raises(ValueError):
            scheduling_service.approve_schedule(
                db=session,
                user_id=user_id,
                request=ScheduleApprovalRequest(schedule_id=proposal.id),
            )


# ============================================================================
# 4. TASK 9: REST API ENDPOINTS
# ============================================================================

def test_api_availability_endpoint(client, test_user):
    resp = client.get(
        "/api/v1/scheduling/availability?horizon_days=2",
        headers={"X-User-Id": str(test_user)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "available_windows" in data
    assert "busy_blocks" in data
    assert data["total_available_minutes"] > 0


def test_api_generate_preview_modify_approve_lifecycle(client, user_with_calendar):
    integration_id, user_id = user_with_calendar
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if base_date.weekday() >= 5:
        base_date += timedelta(days=2)

    # 1. Create a task
    with Session(engine) as session:
        task = Task(
            user_id=user_id,
            title="API End-to-End Scheduled Task",
            priority=TaskPriority.HIGH,
            estimated_minutes=45,
            status=TaskStatus.PENDING,
        )
        session.add(task)
        session.commit()
        task_id = task.id

    # 2. POST /api/v1/scheduling/generate
    gen_resp = client.post(
        "/api/v1/scheduling/generate",
        json={
            "start_date": base_date.isoformat(),
            "horizon_days": 1,
            "task_ids": [str(task_id)],
        },
        headers={"X-User-Id": str(user_id)},
    )
    assert gen_resp.status_code == 201
    gen_data = gen_resp.json()
    assert gen_data["status"] == "DRAFT"
    assert len(gen_data["scheduled_items"]) == 1
    schedule_id = gen_data["id"]
    slot_id = gen_data["scheduled_items"][0]["slot_id"]

    # 3. POST /api/v1/scheduling/preview
    prev_resp = client.post(
        "/api/v1/scheduling/preview",
        json={"schedule_id": schedule_id},
        headers={"X-User-Id": str(user_id)},
    )
    assert prev_resp.status_code == 200
    assert prev_resp.json()["id"] == schedule_id

    # 4. PATCH /api/v1/scheduling/modify
    new_start = base_date.replace(hour=14, minute=0)
    new_end = base_date.replace(hour=14, minute=45)
    mod_resp = client.patch(
        "/api/v1/scheduling/modify",
        json={
            "schedule_id": schedule_id,
            "slot_id": slot_id,
            "new_start_time": new_start.isoformat(),
            "new_end_time": new_end.isoformat(),
        },
        headers={"X-User-Id": str(user_id)},
    )
    assert mod_resp.status_code == 200
    mod_data = mod_resp.json()
    assert mod_data["scheduled_items"][0]["duration_minutes"] == 45

    # 5. POST /api/v1/scheduling/approve
    mock_cal_evt = CalendarEventDTO(
        event_id="goog-api-committed-1",
        calendar_id="primary",
        provider="google_calendar",
        title="Focus: API End-to-End Scheduled Task",
        start_time=new_start,
        end_time=new_end,
    )
    with patch.object(GoogleCalendarProvider, "create_event", return_value=mock_cal_evt):
        appr_resp = client.post(
            "/api/v1/scheduling/approve",
            json={"schedule_id": schedule_id, "target_provider": "google_calendar"},
            headers={"X-User-Id": str(user_id)},
        )
        assert appr_resp.status_code == 200
        appr_data = appr_resp.json()
        assert appr_data["success"] is True
        assert appr_data["status"] == "COMMITTED"
        assert appr_data["events_created"] == 1
