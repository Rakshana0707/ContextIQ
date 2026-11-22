import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import (
    DetectedInterruptionType,
    InterruptionFeedbackClassification,
    InterruptionSeverity,
    InterruptionType,
)
from app.schemas.base import ORMBase


# --- Manual Interruption Schemas (Existing) ---

class InterruptionBase(BaseModel):
    task_id: Optional[uuid.UUID] = None
    interruption_type: InterruptionType
    occurred_at: Optional[datetime] = None
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    location_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(default=None, max_length=5000)


class InterruptionCreate(InterruptionBase):
    pass


class InterruptionRead(ORMBase, InterruptionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    occurred_at: datetime
    created_at: datetime


# --- Automated Interruption Detection Schemas (Phase 3.5) ---

class DetectedInterruptionFeedbackCreate(BaseModel):
    feedback_classification: InterruptionFeedbackClassification
    notes: Optional[str] = Field(default=None, max_length=2000)


class DetectedInterruptionFeedbackRead(ORMBase):
    id: uuid.UUID
    interruption_id: uuid.UUID
    user_id: uuid.UUID
    feedback_classification: InterruptionFeedbackClassification
    notes: Optional[str] = None
    created_at: datetime


class DetectedInterruptionBase(BaseModel):
    interruption_type: DetectedInterruptionType
    severity: InterruptionSeverity = InterruptionSeverity.LOW
    start_timestamp: datetime
    end_timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    detection_method: str = "RULE_BASED_HEURISTIC"
    detection_version: str = "1.0.0"
    explanation: str
    primary_app: Optional[str] = None
    interrupting_app: Optional[str] = None
    resumption_lag_seconds: Optional[float] = None
    source_event_ids: List[str] = Field(default_factory=list)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class DetectedInterruptionCreate(DetectedInterruptionBase):
    user_id: uuid.UUID


class DetectedInterruptionRead(ORMBase, DetectedInterruptionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    feedback: List[DetectedInterruptionFeedbackRead] = Field(default_factory=list)


class DetectedInterruptionsQueryResponse(BaseModel):
    items: List[DetectedInterruptionRead]
    total: int
    limit: int
    offset: int


class InterruptionDetectionMetricsResponse(BaseModel):
    total_detected: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    total_feedback_count: int
    feedback_breakdown: dict[str, int]
    accuracy_rate: Optional[float] = None
    false_positive_rate: Optional[float] = None
    average_duration_seconds: Optional[float] = None
    average_resumption_lag_seconds: Optional[float] = None


class InterruptionDetectionBatchTrigger(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    lookback_hours: Optional[int] = Field(default=24, ge=1, le=720)
