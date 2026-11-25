"""Pydantic schemas for unified behavioral timeline and cross-device synchronization (Phase 5.7)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UnifiedTimelineEventDTO(BaseModel):
    """Normalized cross-device event schema representing activity across desktop, mobile, web, and calendars."""
    event_id: str
    source: str = Field(..., description="desktop_agent_windows | mobile_android | mobile_ios | web_nextjs | calendar_google | calendar_microsoft")
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: str = Field("DESKTOP", description="DESKTOP | MOBILE | TABLET | WEB | CALENDAR")
    platform: str = Field("WINDOWS", description="WINDOWS | ANDROID | IOS | MACOS | LINUX | WEB | CLOUD")
    event_type: str = Field(..., description="APP_FOCUS | IDLE_START | IDLE_RETURN | TASK_INTERACTION | INTERRUPTION | CALENDAR_COMMITMENT | DEVICE_TRANSITION")
    occurred_at: datetime = Field(..., description="Client occurrence timestamp normalized to UTC")
    ingested_at: datetime = Field(..., description="Server ingestion timestamp in UTC")
    timezone_offset_minutes: int = Field(0, description="Client timezone offset from UTC in minutes")
    clock_skew_seconds: float = Field(0.0, description="Estimated drift between device clock and server UTC")
    original_event_id: Optional[str] = None
    application_identifier: Optional[str] = None
    task_id: Optional[uuid.UUID] = None
    duration_seconds: Optional[float] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class CrossDeviceSyncRequest(BaseModel):
    """Batch event upload payload from an authorized device."""
    device_id: str
    client_timestamp: datetime = Field(..., description="Current client clock timestamp for skew estimation")
    events: List[Dict[str, Any]] = Field(..., description="List of raw or normalized client events")


class CrossDeviceSyncResponse(BaseModel):
    received: int
    ingested: int
    dropped_duplicates: int
    estimated_clock_skew_seconds: float
    sync_status: str = "SYNCED"
    processed_at: datetime


class CrossDeviceSessionRead(BaseModel):
    """Reconstructed work session spanning one or more devices."""
    session_id: uuid.UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float
    primary_device_type: str
    device_transitions_count: int
    device_time_breakdown: Dict[str, float] = Field(default_factory=dict, description="Active seconds spent on each device type")
    cross_device_interruption_seconds: float = Field(0.0, description="Interruption duration on secondary device (e.g. mobile phone during desktop work)")
    continuity_score: float = Field(1.0, description="0.0 to 1.0 session coherence score")
    timeline_segments: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
