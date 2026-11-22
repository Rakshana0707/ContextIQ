import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import ORMBase


class SessionTimelineSegment(BaseModel):
    """Granular chronological block within a reconstructed session."""
    segment_id: str
    segment_type: str  # FOCUS, APPLICATION_SWITCH, IDLE, INTERRUPTION, PAUSE
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float
    application_identifier: Optional[str] = None
    task_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class ContextSessionBase(BaseModel):
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str = "COMPLETED"

    # Multi-Application Metrics
    primary_application: Optional[str] = None
    secondary_applications: List[str] = Field(default_factory=list)
    application_breakdown: Dict[str, float] = Field(default_factory=dict)
    transition_count: int = 0
    context_switch_frequency: float = 0.0

    # Timing Durations (seconds)
    focused_time_seconds: float = 0.0
    interruption_time_seconds: float = 0.0
    idle_time_seconds: float = 0.0
    resume_delay_seconds: Optional[float] = None

    # Aggregates
    task_count: int = 0
    interruption_count: int = 0

    # Task Association
    task_id: Optional[uuid.UUID] = None
    task_association_status: str = "UNKNOWN"
    task_association_confidence: Optional[float] = None
    suggested_task_id: Optional[uuid.UUID] = None

    # Quality & Confidence
    reconstruction_confidence: float = 1.0
    quality_tier: str = "HIGH"
    quality_details: Dict[str, Any] = Field(default_factory=dict)

    # Correction
    user_corrected: bool = False
    user_correction_notes: Optional[str] = None


class ContextSessionRead(ORMBase, ContextSessionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    location_id: Optional[uuid.UUID] = None
    context_tag: Optional[str] = None
    created_at: datetime
    last_reconstructed_at: Optional[datetime] = None


class ContextSessionListResponse(BaseModel):
    items: List[ContextSessionRead]
    total: int
    limit: int
    offset: int


class ContextSessionTimelineResponse(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_duration_seconds: float
    focused_time_seconds: float
    interruption_time_seconds: float
    idle_time_seconds: float
    primary_application: Optional[str] = None
    task_id: Optional[uuid.UUID] = None
    timeline: List[SessionTimelineSegment] = Field(default_factory=list)


class ContextSessionCorrectionRequest(BaseModel):
    task_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class SessionReconstructionTriggerRequest(BaseModel):
    lookback_hours: Optional[int] = Field(default=24, ge=1, le=720)
    force_full_rebuild: bool = False
