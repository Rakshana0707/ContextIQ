"""
Standardized Event and Proactive Intelligence Schemas (ContextIQ Phase 7.3).
Provides unified event contracts, validation, dead-letter contracts,
and proactive intelligence feed schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StandardEventType(str, Enum):
    # Context & thrashing
    CONTEXT_SWITCH = "CONTEXT_SWITCH"
    THRASHING_DETECTED = "THRASHING_DETECTED"

    # Task transitions
    TASK_STATE_CHANGED = "TASK_STATE_CHANGED"
    TASK_RESUMED = "TASK_RESUMED"
    MISSED_RESUMPTION = "MISSED_RESUMPTION"

    # Behavioral & Cognitive ML indicators
    FORGETTING_RISK_SPIKE = "FORGETTING_RISK_SPIKE"
    RECOVERY_LAG_EXCEEDED = "RECOVERY_LAG_EXCEEDED"
    CALENDAR_OVERLOAD = "CALENDAR_OVERLOAD"
    BFI_SPIKE = "BFI_SPIKE"
    FOCUS_PATTERN_DRIFT = "FOCUS_PATTERN_DRIFT"
    INTERRUPTION_BURST = "INTERRUPTION_BURST"

    # Manual or user event
    MANUAL_USER_EVENT = "MANUAL_USER_EVENT"


class EventSource(str, Enum):
    DESKTOP_TELEMETRY = "desktop_telemetry"
    MOBILE_COMPANION = "mobile_companion"
    TASK_SERVICE = "task_service"
    CALENDAR_SYNC = "calendar_sync"
    INTELLIGENCE_ENGINE = "intelligence_engine"
    BEHAVIORAL_TWIN = "behavioral_twin"
    USER_MANUAL = "user_manual"


class FeedItemStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SNOOZED = "SNOOZED"
    DISMISSED = "DISMISSED"
    ACTIONED = "ACTIONED"


class DeadLetterStatus(str, Enum):
    PENDING = "PENDING"
    RETRIED = "RETRIED"
    RESOLVED = "RESOLVED"
    DISCARDED = "DISCARDED"


class StandardEvent(BaseModel):
    """
    Standardized, unified event structure for ContextIQ.
    All system events, telemetry, and external integrations normalize to this schema.
    """
    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(..., description="Standardized event type name")
    user_id: uuid.UUID = Field(..., description="Target user identifier")
    device_id: Optional[str] = Field(default=None, description="Source device ID if available")
    event_timestamp: datetime = Field(..., description="UTC timestamp when the event occurred")
    ingestion_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the event was ingested"
    )
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    source: str = Field(default=EventSource.DESKTOP_TELEMETRY.value)
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload parameters")
    correlation_id: Optional[str] = Field(default=None, description="Distributed correlation ID")
    idempotency_key: Optional[str] = Field(default=None, description="Unique deduplication key")

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def populate_idempotency_key(cls, v: Optional[str], info: Any) -> Optional[str]:
        if v:
            return v
        return None


class EventIngestRequest(BaseModel):
    """Public ingest schema allowing client/agent event submission."""
    event_type: str
    user_id: uuid.UUID
    device_id: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    source: Optional[str] = EventSource.DESKTOP_TELEMETRY.value
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class EventProcessingResult(BaseModel):
    event_id: str
    status: str  # PROCESSED, DUPLICATE, FILTERED, DEAD_LETTER, DELAYED
    is_duplicate: bool = False
    rules_matched: int = 0
    executions_created: int = 0
    proactive_feed_item_created: bool = False
    proactive_feed_item_id: Optional[uuid.UUID] = None
    suppressed_by_fatigue: bool = False
    rationale: Optional[str] = None


class ProactiveActionRequest(BaseModel):
    action: str = Field(..., description="'APPROVE', 'SNOOZE', or 'DISMISS'")
    snooze_minutes: Optional[int] = Field(default=60, ge=5, le=1440)


class ProactiveFeedItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    event_id: Optional[str] = None
    detection_type: str
    title: str
    why_it_matters: str
    related_task_id: Optional[uuid.UUID] = None
    related_context: Dict[str, Any] = Field(default_factory=dict)
    recommended_response: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    uncertainty_lower_bound: float
    uncertainty_upper_bound: float
    conformal_interval_text: str
    status: str
    requires_approval: bool = True
    suggested_action: Optional[Dict[str, Any]] = None
    snoozed_until: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DeadLetterRecordSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    raw_payload: Dict[str, Any]
    error_code: str
    error_reason: str
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    updated_at: datetime
