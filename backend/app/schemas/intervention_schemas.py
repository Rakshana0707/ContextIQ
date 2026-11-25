"""
Pydantic v2 schemas for Personalized Intervention Recommendation Engine (Phase 4.5).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import ORMBase


class InterventionCategory(str, Enum):
    FOCUS = "FOCUS"
    RECOVERY = "RECOVERY"
    TASK = "TASK"
    CONTEXTUAL = "CONTEXTUAL"
    WORKLOAD = "WORKLOAD"


class InterventionType(str, Enum):
    # A. Focus
    SUGGEST_PROTECTED_FOCUS_SESSION = "SUGGEST_PROTECTED_FOCUS_SESSION"
    REDUCE_APPLICATION_SWITCHING = "REDUCE_APPLICATION_SWITCHING"
    SELECT_SUITABLE_FOCUS_WINDOW = "SELECT_SUITABLE_FOCUS_WINDOW"

    # B. Recovery
    SUGGEST_RECOVERY_BUFFER = "SUGGEST_RECOVERY_BUFFER"
    RESUME_PREVIOUS_TASK = "RESUME_PREVIOUS_TASK"
    REVIEW_LAST_COMPLETED_STEP = "REVIEW_LAST_COMPLETED_STEP"

    # C. Task
    BREAK_LARGE_TASK = "BREAK_LARGE_TASK"
    REVIEW_APPROACHING_DEADLINE = "REVIEW_APPROACHING_DEADLINE"
    POSTPONE_LOW_PRIORITY_TASK = "POSTPONE_LOW_PRIORITY_TASK"

    # D. Contextual
    COMPLETE_ASSOCIATED_TASKS_LOCATION_EXIT = "COMPLETE_ASSOCIATED_TASKS_LOCATION_EXIT"
    PREPARE_SESSION_MATERIALS = "PREPARE_SESSION_MATERIALS"
    BATCH_RELATED_TASKS = "BATCH_RELATED_TASKS"

    # E. Workload
    REDISTRIBUTE_TASKS = "REDISTRIBUTE_TASKS"
    REVIEW_COMPETING_DEADLINES = "REVIEW_COMPETING_DEADLINES"
    REDUCE_EXCESSIVE_TASK_SWITCHING = "REDUCE_EXCESSIVE_TASK_SWITCHING"


class InterventionLifecycleStatus(str, Enum):
    GENERATED = "GENERATED"
    PRESENTED = "PRESENTED"
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"
    DEFERRED = "DEFERRED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"
    OUTCOME_PENDING = "OUTCOME_PENDING"


class EstimatedEffort(str, Enum):
    LOW = "LOW"        # 1-2 min micro-action
    MEDIUM = "MEDIUM"  # 5-10 min reset / triage
    HIGH = "HIGH"      # >15 min restructuring / planning


class InterventionRead(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    associated_task_id: Optional[uuid.UUID] = None
    intervention_type: str
    intervention_category: str
    title: str
    message: str
    trigger_condition: str
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str
    estimated_effort: str
    relevance_score: float = Field(..., ge=0.0, le=100.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    lifecycle_status: str
    creation_timestamp: datetime
    expiration_timestamp: datetime
    deferred_until: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_feedback_note: Optional[str] = None


class InterventionGenerateRequest(BaseModel):
    as_of: Optional[datetime] = None
    context_tag: Optional[str] = None
    active_hour: Optional[int] = None
    max_interventions: int = Field(3, ge=1, le=10)


class InterventionActionRequest(BaseModel):
    feedback_note: Optional[str] = None
    defer_minutes: Optional[int] = Field(30, ge=5, le=1440)


class InterventionResponse(BaseModel):
    user_id: uuid.UUID
    generated_at: datetime
    interventions: List[InterventionRead]
    summary_insights: List[str] = Field(default_factory=list)
