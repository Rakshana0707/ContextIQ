"""Pydantic schemas for calendar-aware intelligent task scheduling engine."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BusyBlockRead(BaseModel):
    """Normalized busy block restricting availability (meeting, break, or recovery buffer)."""
    title: str
    start_time: datetime
    end_time: datetime
    source: str  # google_calendar | microsoft_outlook | working_hours | lunch_break | recovery_buffer
    is_recovery_buffer: bool = False


class AvailabilityWindowRead(BaseModel):
    """Free time interval available for cognitive work or chores."""
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    focus_quality_score: float = 50.0
    is_peak_focus: bool = False


class UserAvailabilityResponse(BaseModel):
    """Aggregated free vs busy availability windows across connected calendars and working hours."""
    user_id: uuid.UUID
    horizon_start: datetime
    horizon_end: datetime
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    total_available_minutes: int
    available_windows: List[AvailabilityWindowRead]
    busy_blocks: List[BusyBlockRead]


class ScheduleExplanationDTO(BaseModel):
    """Explainable behavioral rationale behind a scheduled task placement."""
    primary_rationale: str
    behavioral_drivers: List[str] = Field(default_factory=list)
    calendar_constraints: List[str] = Field(default_factory=list)
    rejected_alternatives: List[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class ScheduledSlotDTO(BaseModel):
    """A scheduled task allocation inside a validated availability window."""
    slot_id: str
    task_id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    priority: str
    context_tag: Optional[str] = None
    due_at: Optional[datetime] = None
    is_deep_work: bool = False
    focus_quality_score: float = 50.0
    explanation: ScheduleExplanationDTO


class UnscheduledTaskDTO(BaseModel):
    """Task that could not be placed due to window deficits, deadlines, or dependencies."""
    task_id: uuid.UUID
    title: str
    priority: str
    due_at: Optional[datetime] = None
    estimated_minutes: int
    reason_code: str  # INSUFFICIENT_WINDOW | DEADLINE_CANNOT_BE_MET | DEPENDENCY_UNRESOLVED
    reason_detail: str


class ScheduleGenerateRequest(BaseModel):
    """Parameters to generate a personalized task schedule draft."""
    start_date: Optional[datetime] = None
    horizon_days: int = Field(3, ge=1, le=14)
    working_hour_start: int = Field(9, ge=0, le=23)
    working_hour_end: int = Field(17, ge=1, le=24)
    include_weekends: bool = False
    enforce_lunch_break: bool = True
    lunch_start_hour: int = Field(12, ge=11, le=14)
    lunch_duration_minutes: int = Field(60, ge=15, le=120)
    recovery_buffer_minutes: int = Field(15, ge=0, le=60)
    task_ids: Optional[List[uuid.UUID]] = None


class ScheduleProposalResponse(BaseModel):
    """Complete explainable schedule proposal presented to the user for preview or decision."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    horizon_start: datetime
    horizon_end: datetime
    scheduled_items: List[ScheduledSlotDTO]
    unscheduled_items: List[UnscheduledTaskDTO]
    total_scheduled_minutes: int
    total_tasks_scheduled: int
    focus_alignment_rate: float
    created_at: datetime


class ScheduleApprovalRequest(BaseModel):
    """User approval request to commit scheduled focus blocks to their external calendar."""
    schedule_id: uuid.UUID
    target_provider: Optional[str] = None  # google_calendar | microsoft_outlook | None (auto-detect)
    calendar_id: str = "primary"
    include_task_ids: Optional[List[uuid.UUID]] = None


class ScheduleApprovalResponse(BaseModel):
    """Result of committing approved task schedule to external calendar."""
    success: bool
    schedule_id: uuid.UUID
    status: str
    events_created: int
    calendar_provider: str
    created_event_ids: List[str]
    message: str


class ScheduleRejectRequest(BaseModel):
    """Rejection request to discard a schedule proposal."""
    schedule_id: uuid.UUID
    reason: Optional[str] = None


class ScheduleModifySlotRequest(BaseModel):
    """Reschedule or modify a specific task slot in a draft proposal."""
    schedule_id: uuid.UUID
    slot_id: str
    new_start_time: datetime
    new_end_time: datetime
