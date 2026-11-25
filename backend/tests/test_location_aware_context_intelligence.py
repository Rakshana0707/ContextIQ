"""Automated test suite for Location-Aware Contextual Intelligence and Smart Reminders (Phase 5.8)."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory and project root to sys.path
backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

# Teach SQLite how to compile Postgres JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

os.environ["SECRET_KEY"] = "test-secret-phase58-location-intelligence"
os.environ["DATABASE_URL"] = "sqlite:///./_test_location_context.db"

from app.db.session import Base, engine
from app.main import app
from app.models.enums import LocationType, RoutineAssociationSource, TaskPriority, TaskStatus
from app.models.location import Location
from app.models.location_checkin import LocationCheckIn
from app.models.location_routine_association import LocationRoutineAssociation
from app.models.task import Task
from app.models.user import User
from app.schemas.location_context import (
    LocationCheckInCreate,
    LocationContextCreate,
)
from app.services.location_context_service import LocationContextService

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    LocationRoutineAssociation.__table__.drop(bind=engine, checkfirst=True)
    LocationCheckIn.__table__.drop(bind=engine, checkfirst=True)
    Location.__table__.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        session.query(LocationRoutineAssociation).delete()
        session.query(LocationCheckIn).delete()
        session.query(Task).delete()
        session.query(Location).delete()
        session.commit()
    yield


@pytest.fixture
def test_user():
    uid = uuid.uuid4()
    with Session(engine) as session:
        user = User(
            id=uid,
            email=f"locuser_{uid.hex[:6]}@contextiq.ai",
            hashed_password="test_hashed_password",
            display_name="Location Context User",
            is_active=True,
        )
        session.add(user)
        session.commit()
    return uid


# ============================================================================
# 1. TASK 2: USER-DEFINED LOCATION MANAGEMENT & DELETION
# ============================================================================

def test_location_lifecycle_and_category_management(test_user):
    """Verifies creation, listing, and deletion of user-defined places across categories."""
    with Session(engine) as session:
        # Create Home, Campus, Office, Library, Laboratory
        campus_payload = LocationContextCreate(
            name="University Campus",
            location_type=LocationType.CAMPUS,
            latitude=37.4275,
            longitude=-122.1697,
            radius_meters=200,
            reminders_enabled=True,
            arrival_reminder_enabled=True,
            departure_reminder_enabled=True,
        )
        library_payload = LocationContextCreate(
            name="Green Library",
            location_type=LocationType.LIBRARY,
            latitude=37.4280,
            longitude=-122.1680,
            radius_meters=100,
            reminders_enabled=True,
        )
        office_payload = LocationContextCreate(
            name="Tech Lab",
            location_type=LocationType.LABORATORY,
            radius_meters=150,
            reminders_enabled=True,
        )

        campus = LocationContextService.create_location(session, test_user, campus_payload)
        library = LocationContextService.create_location(session, test_user, library_payload)
        office = LocationContextService.create_location(session, test_user, office_payload)

        # List locations
        locations = LocationContextService.list_locations(session, test_user, active_only=True)
        assert len(locations) == 3
        loc_names = [l.name for l in locations]
        assert "University Campus" in loc_names
        assert "Green Library" in loc_names
        assert "Tech Lab" in loc_names

        # Delete campus
        LocationContextService.delete_location(session, test_user, campus.id)
        remaining = LocationContextService.list_locations(session, test_user, active_only=True)
        assert len(remaining) == 2
        assert "University Campus" not in [l.name for l in remaining]


# ============================================================================
# 2. TASK 3 & 8: PRIVACY CONSENT & NOTIFICATION SUPPRESSION
# ============================================================================

def test_privacy_consent_and_notification_suppression(test_user):
    """Ensures reminders are suppressed when location consent is disabled, or during quiet hours/focus sessions."""
    with Session(engine) as session:
        loc = LocationContextService.create_location(
            session,
            test_user,
            LocationContextCreate(
                name="Headquarters",
                location_type=LocationType.OFFICE,
            ),
        )

        # Create a pending task linked to this location
        task = Task(
            id=uuid.uuid4(),
            user_id=test_user,
            title="Review quarterly strategy",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            context_location_id=loc.id,
        )
        session.add(task)
        session.commit()

        # 1. Location Consent Disabled: must return 0 reminders
        resp_no_consent = LocationContextService.get_location_recommendations(
            session,
            test_user,
            location_id=loc.id,
            location_consent_enabled=False,
        )
        assert len(resp_no_consent.reminders) == 0

        # 2. Quiet Hours (23:30 at night): must suppress reminders
        night_time = datetime(2026, 11, 24, 23, 30, tzinfo=timezone.utc)
        resp_quiet = LocationContextService.get_location_recommendations(
            session,
            test_user,
            location_id=loc.id,
            as_of=night_time,
            quiet_hours_enabled=True,
        )
        assert resp_quiet.quiet_hours_active is True
        assert len(resp_quiet.reminders) == 0
        assert resp_quiet.suppressed_count >= 1

        # 3. In Deep Focus Session (Daytime): must suppress non-critical reminders
        day_time = datetime(2026, 11, 24, 14, 0, tzinfo=timezone.utc)
        resp_focus = LocationContextService.get_location_recommendations(
            session,
            test_user,
            location_id=loc.id,
            as_of=day_time,
            is_in_focus_session=True,
        )
        assert resp_focus.focus_session_active is True
        assert len(resp_focus.reminders) == 0
        assert resp_focus.suppressed_count >= 1


# ============================================================================
# 3. TASK 4 & 7: CONTEXT ASSOCIATION & ROUTINE DISCOVERY
# ============================================================================

def test_context_association_and_routine_discovery_tiers(test_user):
    """
    Verifies routine discovery distinguishes:
      - EXPLICIT: directly bound task
      - STATISTICALLY_OBSERVED: >= 3 completions in context
      - LOW_CONFIDENCE: < 3 completions
    """
    with Session(engine) as session:
        loc = LocationContextService.create_location(
            session,
            test_user,
            LocationContextCreate(
                name="Campus Library",
                location_type=LocationType.LIBRARY,
            ),
        )

        # 1. Explicit task binding
        explicit_task = Task(
            id=uuid.uuid4(),
            user_id=test_user,
            title="Read literature survey",
            status=TaskStatus.PENDING,
            context_location_id=loc.id,
            context_tag="research",
        )
        # 2. Add 3 completed tasks with context_tag "research" (Simulating historical habit)
        for i in range(3):
            ct = Task(
                id=uuid.uuid4(),
                user_id=test_user,
                title=f"Completed research item {i+1}",
                status=TaskStatus.COMPLETED,
                context_location_id=loc.id,
                context_tag="research",
            )
            session.add(ct)

        # 3. Add 1 completed task with context_tag "casual_reading" (< 3 observations)
        ct_low = Task(
            id=uuid.uuid4(),
            user_id=test_user,
            title="Skim magazine",
            status=TaskStatus.COMPLETED,
            context_location_id=loc.id,
            context_tag="casual_reading",
        )
        session.add_all([explicit_task, ct_low])
        session.commit()

        # Run routine discovery
        routines = LocationContextService.discover_location_routines(session, test_user, loc.id)
        assert len(routines) >= 2

        sources = {r.association_source for r in routines}
        assert RoutineAssociationSource.EXPLICIT.value in sources
        assert RoutineAssociationSource.STATISTICALLY_OBSERVED.value in sources
        assert RoutineAssociationSource.LOW_CONFIDENCE.value in sources

        # Verify observed category has high confidence
        observed_routine = next(
            r for r in routines if r.association_source == RoutineAssociationSource.STATISTICALLY_OBSERVED.value
        )
        assert observed_routine.confidence_score >= 0.5
        assert observed_routine.observation_count >= 3


# ============================================================================
# 4. TASK 5 & 6: LOCATION REMINDERS, GEOFENCING, & DEBOUNCING
# ============================================================================

def test_smart_reminders_and_geofence_debouncing(test_user):
    """
    Tests arrival reminders, departure 'One More Thing' reminders,
    and debouncing of rapid geofence oscillations.
    """
    now = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
    with Session(engine) as session:
        loc = LocationContextService.create_location(
            session,
            test_user,
            LocationContextCreate(
                name="Main Quad",
                location_type=LocationType.CAMPUS,
            ),
        )

        # Add an arrival reading task and a departure closure task
        task_arrival = Task(
            id=uuid.uuid4(),
            user_id=test_user,
            title="Attend Physics Seminar",
            status=TaskStatus.PENDING,
            context_location_id=loc.id,
        )
        task_departure = Task(
            id=uuid.uuid4(),
            user_id=test_user,
            title="Obtain Advisor Thesis Signature",
            status=TaskStatus.PENDING,
            context_location_id=loc.id,
        )
        session.add_all([task_arrival, task_departure])
        session.commit()

        # 1. Geofence Enter / Arrival
        cin1, is_dup1 = LocationContextService.record_check_in(
            session,
            test_user,
            LocationCheckInCreate(
                location_id=loc.id,
                check_in_type="GEOFENCE_ENTER",
                occurred_at=now,
            ),
        )
        assert is_dup1 is False
        assert cin1.check_in_type == "GEOFENCE_ENTER"

        arrival_recs = LocationContextService.get_location_recommendations(
            session,
            test_user,
            location_id=loc.id,
            trigger_type="ARRIVAL",
            as_of=now,
        )
        assert arrival_recs.total_reminders >= 1
        assert any("Arrived at Main Quad" in r.message for r in arrival_recs.reminders)

        # 2. Jitter Debounce: immediate second GEOFENCE_ENTER within 2 minutes must be debounced
        cin2, is_dup2 = LocationContextService.record_check_in(
            session,
            test_user,
            LocationCheckInCreate(
                location_id=loc.id,
                check_in_type="GEOFENCE_ENTER",
                occurred_at=now + timedelta(minutes=2),
            ),
        )
        assert is_dup2 is True

        # 3. Geofence Exit / Departure ("One More Thing")
        departure_time = now + timedelta(hours=2)
        cin3, is_dup3 = LocationContextService.record_check_in(
            session,
            test_user,
            LocationCheckInCreate(
                location_id=loc.id,
                check_in_type="GEOFENCE_EXIT",
                occurred_at=departure_time,
            ),
        )
        assert is_dup3 is False
        assert cin3.check_in_type == "GEOFENCE_EXIT"

        departure_recs = LocationContextService.get_location_recommendations(
            session,
            test_user,
            location_id=loc.id,
            trigger_type="DEPARTURE",
            as_of=departure_time,
        )
        assert departure_recs.total_reminders >= 1
        dep_reminder = departure_recs.reminders[0]
        assert "Before leaving Main Quad" in dep_reminder.message
        assert dep_reminder.recommendation_arm == "arm_3_one_more_thing"


# ============================================================================
# 5. TASK 9: REST API ENDPOINTS INTEGRATION
# ============================================================================

def test_api_context_locations_and_checkins_lifecycle(test_user):
    """
    Tests REST API endpoints:
      - GET /api/v1/context/locations
      - POST /api/v1/context/locations
      - DELETE /api/v1/context/locations/{id}
      - POST /api/v1/context/check-ins
      - GET /api/v1/context/location-recommendations
    """
    headers = {"X-User-Id": str(test_user)}

    # 1. POST /api/v1/context/locations
    create_resp = client.post(
        "/api/v1/context/locations",
        json={
            "name": "Biotech Laboratory",
            "location_type": "LABORATORY",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "radius_meters": 120,
            "reminders_enabled": True,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    loc_data = create_resp.json()
    loc_id = loc_data["id"]
    assert loc_data["name"] == "Biotech Laboratory"

    # 2. GET /api/v1/context/locations
    list_resp = client.get("/api/v1/context/locations", headers=headers)
    assert list_resp.status_code == 200
    assert any(l["id"] == loc_id for l in list_resp.json())

    # 3. POST /api/v1/context/check-ins (Manual Check-In)
    checkin_resp = client.post(
        "/api/v1/context/check-ins",
        json={
            "location_id": loc_id,
            "check_in_type": "MANUAL",
            "notes": "Arrived for afternoon spectroscopy run",
        },
        headers=headers,
    )
    assert checkin_resp.status_code == 201
    assert checkin_resp.json()["location_name"] == "Biotech Laboratory"

    # 4. GET /api/v1/context/location-recommendations
    recs_resp = client.get(
        f"/api/v1/context/location-recommendations?location_id={loc_id}&trigger_type=ARRIVAL",
        headers=headers,
    )
    assert recs_resp.status_code == 200
    assert recs_resp.json()["location_name"] == "Biotech Laboratory"

    # 5. DELETE /api/v1/context/locations/{id}
    del_resp = client.delete(f"/api/v1/context/locations/{loc_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify deleted
    list_after = client.get("/api/v1/context/locations", headers=headers)
    assert not any(l["id"] == loc_id for l in list_after.json())
