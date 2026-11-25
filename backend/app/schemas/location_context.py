"""Pydantic schemas for Location-Aware Contextual Intelligence and Smart Reminders (Phase 5.8)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CheckInType, LocationType, RoutineAssociationSource


class LocationContextCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Named place (e.g. Home, Office, Campus, Library)")
    location_type: LocationType = Field(LocationType.OTHER, description="Category of location")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Optional GPS latitude")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Optional GPS longitude")
    radius_meters: Optional[int] = Field(default=150, ge=50, le=5000, description="Geofence boundary radius (minimum 50m)")
    is_active: bool = Field(default=True, description="Whether location is monitored/available")
    reminders_enabled: bool = Field(default=True, description="Master reminder toggle for this location")
    arrival_reminder_enabled: bool = Field(default=True, description="Trigger reminders upon arrival / entry")
    departure_reminder_enabled: bool = Field(default=True, description="Trigger reminders upon departure / exit")


class LocationContextRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    location_type: LocationType
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: Optional[int] = 150
    is_active: bool = True
    reminders_enabled: bool = True
    arrival_reminder_enabled: bool = True
    departure_reminder_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationCheckInCreate(BaseModel):
    location_id: Optional[uuid.UUID] = Field(default=None, description="Linked location ID if known")
    location_name: Optional[str] = Field(default=None, description="Explicit or manual place name")
    check_in_type: CheckInType = Field(CheckInType.MANUAL, description="MANUAL | GEOFENCE_ENTER | GEOFENCE_EXIT")
    device_id: Optional[str] = Field(default=None, description="Hardware device ID triggering the check-in")
    occurred_at: Optional[datetime] = Field(default=None, description="Occurrence timestamp in UTC")
    notes: Optional[str] = Field(default=None, description="Optional user notes")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Edge metadata (distance, geofence radius)")


class LocationCheckInRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    location_id: Optional[uuid.UUID] = None
    location_name: str
    location_type: str
    check_in_type: str
    device_id: Optional[str] = None
    occurred_at: datetime
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationReminderDTO(BaseModel):
    task_id: Optional[uuid.UUID] = None
    title: str
    due_at: Optional[datetime] = None
    priority: str = "MEDIUM"
    trigger_type: str = "ARRIVAL"  # ARRIVAL | DEPARTURE | PRESENCE
    association_source: str = "EXPLICIT"  # EXPLICIT | STATISTICALLY_OBSERVED | LOW_CONFIDENCE
    confidence_score: float = 1.0
    message: str
    recommendation_arm: str = "arm_3_one_more_thing"


class LocationRecommendationsResponse(BaseModel):
    location_id: Optional[uuid.UUID] = None
    location_name: str
    trigger_type: str
    reminders: List[LocationReminderDTO] = Field(default_factory=list)
    total_reminders: int = 0
    quiet_hours_active: bool = False
    focus_session_active: bool = False
    suppressed_count: int = 0


class LocationConsentDTO(BaseModel):
    location_tracking_enabled: bool = True
    allow_geofencing: bool = True
    allow_manual_checkins: bool = True
    permitted_categories: List[str] = Field(
        default_factory=lambda: ["WORK", "OFFICE", "CAMPUS", "LIBRARY", "STUDY"]
    )
