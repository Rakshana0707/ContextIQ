"""Location-Aware Contextual Intelligence and Smart Reminders Service (Phase 5.8)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.enums import CheckInType, LocationType, RoutineAssociationSource, TaskStatus
from app.models.location import Location
from app.models.location_checkin import LocationCheckIn
from app.models.location_routine_association import LocationRoutineAssociation
from app.models.task import Task
from app.schemas.location_context import (
    LocationCheckInCreate,
    LocationContextCreate,
    LocationRecommendationsResponse,
    LocationReminderDTO,
)

logger = logging.getLogger("contextiq.location_context_service")


def _to_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class LocationContextService:
    """Manages user-defined locations, check-ins, routine mining, and smart reminders."""

    # ------------------------------------------------------------------------
    # 1. Location Management
    # ------------------------------------------------------------------------

    @classmethod
    def list_locations(
        cls,
        db: Session,
        user_id: uuid.UUID,
        active_only: bool = True,
    ) -> List[Location]:
        """Lists user-defined places with optional filtering for active places."""
        query = select(Location).where(Location.user_id == user_id)
        if active_only:
            query = query.where(Location.is_active.is_(True))
        return list(db.scalars(query.order_by(Location.name.asc())).all())

    @classmethod
    def create_location(
        cls,
        db: Session,
        user_id: uuid.UUID,
        payload: LocationContextCreate,
    ) -> Location:
        """Creates a user-defined physical location with reminder toggles."""
        loc = Location(
            id=uuid.uuid4(),
            user_id=user_id,
            name=payload.name.strip(),
            location_type=payload.location_type,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius_meters=payload.radius_meters or 150,
            is_active=payload.is_active,
            reminders_enabled=payload.reminders_enabled,
            arrival_reminder_enabled=payload.arrival_reminder_enabled,
            departure_reminder_enabled=payload.departure_reminder_enabled,
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
        logger.info(f"Created location {loc.name} ({loc.id}) for user {user_id}")
        return loc

    @classmethod
    def get_location(
        cls,
        db: Session,
        user_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> Location:
        """Retrieves a single location or raises 404."""
        loc = db.scalar(
            select(Location).where(
                Location.id == location_id,
                Location.user_id == user_id,
            )
        )
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {location_id} not found",
            )
        return loc

    @classmethod
    def delete_location(
        cls,
        db: Session,
        user_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> None:
        """Deletes a user location and cleans up associated routine associations."""
        loc = cls.get_location(db, user_id, location_id)
        # Clean up associations
        db.execute(
            delete(LocationRoutineAssociation).where(
                LocationRoutineAssociation.location_id == location_id
            )
        )
        db.delete(loc)
        db.commit()
        logger.info(f"Deleted location {location_id} for user {user_id}")

    # ------------------------------------------------------------------------
    # 2. Check-In & Boundary Transition Processing (with Debouncing)
    # ------------------------------------------------------------------------

    @classmethod
    def record_check_in(
        cls,
        db: Session,
        user_id: uuid.UUID,
        payload: LocationCheckInCreate,
        min_debounce_seconds: int = 300,  # 5 minutes debounce
    ) -> Tuple[LocationCheckIn, bool]:
        """
        Records a discrete check-in or geofence boundary event.
        Debounces duplicate transitions within min_debounce_seconds to prevent
        GPS jitter oscillations (e.g. rapid bounce at edge of 150m radius).
        Returns: (LocationCheckIn, is_duplicate)
        """
        now = _to_utc(payload.occurred_at)

        # Resolve location metadata
        loc_name = payload.location_name
        loc_type = "OTHER"
        if payload.location_id:
            loc = db.scalar(
                select(Location).where(
                    Location.id == payload.location_id,
                    Location.user_id == user_id,
                )
            )
            if loc:
                loc_name = loc.name
                loc_type = loc.location_type.value if hasattr(loc.location_type, "value") else str(loc.location_type)
        if not loc_name:
            loc_name = "Unspecified Location"

        check_in_type_str = (
            payload.check_in_type.value
            if hasattr(payload.check_in_type, "value")
            else str(payload.check_in_type)
        )

        # Debounce check: recent check-in for the same user & location & transition type
        debounce_threshold = now - timedelta(seconds=min_debounce_seconds)
        recent_check_in = db.scalar(
            select(LocationCheckIn)
            .where(
                LocationCheckIn.user_id == user_id,
                LocationCheckIn.location_name == loc_name,
                LocationCheckIn.check_in_type == check_in_type_str,
                LocationCheckIn.occurred_at >= debounce_threshold,
            )
            .order_by(desc(LocationCheckIn.occurred_at))
        )

        if recent_check_in:
            logger.info(
                f"Debounced duplicate check-in {check_in_type_str} at {loc_name} within {min_debounce_seconds}s"
            )
            return recent_check_in, True

        checkin = LocationCheckIn(
            id=uuid.uuid4(),
            user_id=user_id,
            location_id=payload.location_id,
            location_name=loc_name,
            location_type=loc_type,
            check_in_type=check_in_type_str,
            device_id=payload.device_id,
            occurred_at=now,
            notes=payload.notes,
            payload=payload.payload or {},
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin, False

    # ------------------------------------------------------------------------
    # 3. Association Mining & Routine Discovery
    # ------------------------------------------------------------------------

    @classmethod
    def discover_location_routines(
        cls,
        db: Session,
        user_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None,
    ) -> List[LocationRoutineAssociation]:
        """
        Discovers and updates location-task associations across three evidence tiers:
        1. EXPLICIT: Directly configured by user (Task.context_location_id == location_id)
        2. STATISTICALLY_OBSERVED: Discovered from >= 3 historical completions with confidence >= 0.5
        3. LOW_CONFIDENCE: < 3 observations or confidence < 0.5 (tentative suggestion)
        """
        # Fetch user locations
        loc_query = select(Location).where(Location.user_id == user_id)
        if location_id:
            loc_query = loc_query.where(Location.id == location_id)
        locations = list(db.scalars(loc_query).all())

        discovered: List[LocationRoutineAssociation] = []

        for loc in locations:
            # 1. Explicit associations
            explicit_tasks = list(
                db.scalars(
                    select(Task).where(
                        Task.user_id == user_id,
                        Task.context_location_id == loc.id,
                    )
                ).all()
            )
            for t in explicit_tasks:
                assoc = db.scalar(
                    select(LocationRoutineAssociation).where(
                        LocationRoutineAssociation.user_id == user_id,
                        LocationRoutineAssociation.location_id == loc.id,
                        LocationRoutineAssociation.task_id == t.id,
                        LocationRoutineAssociation.association_source == RoutineAssociationSource.EXPLICIT.value,
                    )
                )
                if not assoc:
                    assoc = LocationRoutineAssociation(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        location_id=loc.id,
                        task_id=t.id,
                        task_category=t.context_tag or "general",
                        trigger_type="ARRIVAL",
                        association_source=RoutineAssociationSource.EXPLICIT.value,
                        confidence_score=1.0,
                        support=1.0,
                        observation_count=1,
                        is_active=True,
                    )
                    db.add(assoc)
                discovered.append(assoc)

            # 2. Historical completion observations
            checkin_count = db.scalar(
                select(LocationCheckIn)
                .where(
                    LocationCheckIn.user_id == user_id,
                    LocationCheckIn.location_id == loc.id,
                )
            )
            # Count completed tasks matching location name or context_tag
            completed_tasks = list(
                db.scalars(
                    select(Task).where(
                        Task.user_id == user_id,
                        Task.status == TaskStatus.COMPLETED,
                        (Task.context_location_id == loc.id) | (Task.context_tag == loc.name.lower()),
                    )
                ).all()
            )

            # Evaluate frequency
            freq_by_category: Dict[str, int] = {}
            for ct in completed_tasks:
                cat = ct.context_tag or "general"
                freq_by_category[cat] = freq_by_category.get(cat, 0) + 1

            for cat, count in freq_by_category.items():
                if count >= 3:
                    source = RoutineAssociationSource.STATISTICALLY_OBSERVED.value
                    confidence = min(0.9, 0.5 + (count * 0.05))
                    support = min(1.0, count / 10.0)
                else:
                    source = RoutineAssociationSource.LOW_CONFIDENCE.value
                    confidence = round(count * 0.2, 2)
                    support = round(count * 0.1, 2)

                assoc = db.scalar(
                    select(LocationRoutineAssociation).where(
                        LocationRoutineAssociation.user_id == user_id,
                        LocationRoutineAssociation.location_id == loc.id,
                        LocationRoutineAssociation.task_category == cat,
                        LocationRoutineAssociation.association_source == source,
                    )
                )
                if not assoc:
                    assoc = LocationRoutineAssociation(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        location_id=loc.id,
                        task_id=None,
                        task_category=cat,
                        trigger_type="ARRIVAL",
                        association_source=source,
                        confidence_score=confidence,
                        support=support,
                        observation_count=count,
                        is_active=True,
                    )
                    db.add(assoc)
                else:
                    assoc.observation_count = count
                    assoc.confidence_score = confidence
                    assoc.support = support
                discovered.append(assoc)

        db.commit()
        return discovered

    # ------------------------------------------------------------------------
    # 4. Smart Reminders & Contextual Recommendations
    # ------------------------------------------------------------------------

    @classmethod
    def get_location_recommendations(
        cls,
        db: Session,
        user_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None,
        location_name: Optional[str] = None,
        trigger_type: str = "ARRIVAL",  # ARRIVAL | DEPARTURE | MANUAL
        as_of: Optional[datetime] = None,
        is_in_focus_session: bool = False,
        quiet_hours_enabled: bool = True,
        location_consent_enabled: bool = True,
    ) -> LocationRecommendationsResponse:
        """
        Generates smart contextual reminders based on current location and trigger type.
        Applies privacy guardrails, quiet hours, and focus session suppression.
        """
        now = _to_utc(as_of)

        # 1. Privacy Guardrail: Check consent
        if not location_consent_enabled:
            return LocationRecommendationsResponse(
                location_id=location_id,
                location_name=location_name or "Unknown",
                trigger_type=trigger_type,
                reminders=[],
                total_reminders=0,
                quiet_hours_active=False,
                focus_session_active=False,
                suppressed_count=0,
            )

        # 2. Quiet Hours Guardrail (Default: 22:00 to 08:00)
        is_quiet_hours = False
        if quiet_hours_enabled:
            current_hour = now.hour
            if current_hour >= 22 or current_hour < 8:
                is_quiet_hours = True

        # Resolve location details
        loc: Optional[Location] = None
        if location_id:
            loc = db.scalar(
                select(Location).where(
                    Location.id == location_id,
                    Location.user_id == user_id,
                )
            )
        elif location_name:
            loc = db.scalar(
                select(Location).where(
                    Location.user_id == user_id,
                    Location.name.ilike(location_name.strip()),
                )
            )

        target_name = loc.name if loc else (location_name or "Current Location")
        target_id = loc.id if loc else location_id

        # Check if reminders are disabled on this specific location
        if loc and not loc.reminders_enabled:
            return LocationRecommendationsResponse(
                location_id=target_id,
                location_name=target_name,
                trigger_type=trigger_type,
                reminders=[],
                total_reminders=0,
                quiet_hours_active=is_quiet_hours,
                focus_session_active=is_in_focus_session,
                suppressed_count=0,
            )

        # Check trigger-specific toggles
        if loc:
            if trigger_type == "ARRIVAL" and not loc.arrival_reminder_enabled:
                return LocationRecommendationsResponse(
                    location_id=target_id,
                    location_name=target_name,
                    trigger_type=trigger_type,
                    reminders=[],
                    total_reminders=0,
                    quiet_hours_active=is_quiet_hours,
                    focus_session_active=is_in_focus_session,
                    suppressed_count=0,
                )
            if trigger_type == "DEPARTURE" and not loc.departure_reminder_enabled:
                return LocationRecommendationsResponse(
                    location_id=target_id,
                    location_name=target_name,
                    trigger_type=trigger_type,
                    reminders=[],
                    total_reminders=0,
                    quiet_hours_active=is_quiet_hours,
                    focus_session_active=is_in_focus_session,
                    suppressed_count=0,
                )

        # Query pending tasks associated with this location
        task_query = select(Task).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.PAUSED]),
        )
        if target_id:
            task_query = task_query.where(
                (Task.context_location_id == target_id)
                | (Task.context_tag.ilike(target_name.lower()))
            )
        else:
            task_query = task_query.where(Task.context_tag.ilike(target_name.lower()))

        candidate_tasks = list(db.scalars(task_query.order_by(Task.priority.desc())).all())

        # If suppressed by quiet hours or active focus session, do not dispatch non-critical reminders
        suppressed = 0
        reminders: List[LocationReminderDTO] = []

        for t in candidate_tasks:
            # If in deep focus or quiet hours, suppress standard reminders
            if is_quiet_hours or is_in_focus_session:
                suppressed += 1
                continue

            # Format reminder copy based on trigger type
            if trigger_type == "DEPARTURE":
                msg = f"Before leaving {target_name}: '{t.title}' is still pending."
                arm = "arm_3_one_more_thing"
            elif trigger_type == "ARRIVAL":
                msg = f"Arrived at {target_name}: You have pending task '{t.title}'."
                arm = "arm_1_reminder"
            else:
                msg = f"At {target_name}: Contextual task '{t.title}'."
                arm = "arm_1_reminder"

            reminders.append(
                LocationReminderDTO(
                    task_id=t.id,
                    title=t.title,
                    due_at=t.due_at,
                    priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                    trigger_type=trigger_type,
                    association_source="EXPLICIT" if t.context_location_id == target_id else "STATISTICALLY_OBSERVED",
                    confidence_score=1.0 if t.context_location_id == target_id else 0.75,
                    message=msg,
                    recommendation_arm=arm,
                )
            )

        return LocationRecommendationsResponse(
            location_id=target_id,
            location_name=target_name,
            trigger_type=trigger_type,
            reminders=reminders,
            total_reminders=len(reminders),
            quiet_hours_active=is_quiet_hours,
            focus_session_active=is_in_focus_session,
            suppressed_count=suppressed,
        )
