"""
Pydantic v2 schemas for ContextIQ Long-Term Behavioral Memory & Pattern Evolution (Phase 8.3).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.behavioral_memory import (
    MemoryCategory,
    MemorySourceType,
    MemoryValidityStatus,
    PatternEvolutionType,
)


class BehavioralMemoryBase(BaseModel):
    category: MemoryCategory
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    source_type: MemorySourceType = MemorySourceType.MODEL_INFERRED_PATTERN
    validity_status: MemoryValidityStatus = MemoryValidityStatus.ACTIVE
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    expiration_policy: Optional[Dict[str, Any]] = None


class BehavioralMemoryCreate(BaseModel):
    category: MemoryCategory
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    source_type: MemorySourceType = MemorySourceType.EXPLICIT_USER_INSTRUCTION
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    supporting_evidence: Optional[Dict[str, Any]] = None
    expiration_policy: Optional[Dict[str, Any]] = None


class BehavioralMemoryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    validity_status: Optional[MemoryValidityStatus] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_disabled: Optional[bool] = None
    user_correction_notes: Optional[str] = None
    expiration_policy: Optional[Dict[str, Any]] = None


class MemoryCorrectionRequest(BaseModel):
    corrected_description: Optional[str] = None
    user_notes: str = Field(min_length=1, description="Reason for user correction or clarifying details")
    is_inaccurate: bool = Field(default=False, description="Whether this observed pattern is inaccurate")
    validity_status: Optional[MemoryValidityStatus] = None


class PatternEvolutionEventRead(BaseModel):
    timestamp: datetime
    evolution_type: PatternEvolutionType
    previous_status: Optional[str] = None
    new_status: str
    previous_confidence: Optional[float] = None
    new_confidence: float
    reason: str
    evidence_summary: Optional[Dict[str, Any]] = None


class BehavioralMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    category: MemoryCategory
    title: str
    description: str
    source_type: MemorySourceType
    validity_status: MemoryValidityStatus
    confidence: float
    observation_count: int
    reinforcement_count: int
    contradiction_count: int
    first_observed_at: datetime
    last_observed_at: datetime
    last_reinforced_at: Optional[datetime] = None
    last_contradicted_at: Optional[datetime] = None
    supporting_evidence: Dict[str, Any]
    evolution_history: List[Dict[str, Any]]
    expiration_policy: Dict[str, Any]
    is_user_corrected: bool
    user_correction_notes: Optional[str] = None
    is_disabled: bool
    created_at: datetime
    updated_at: datetime


class BehavioralTemporalSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    summary_metrics: Dict[str, Any]
    emerging_pattern_ids: List[str]
    strengthened_pattern_ids: List[str]
    weakened_pattern_ids: List[str]
    outdated_pattern_ids: List[str]
    narrative_summary: Optional[str] = None
    created_at: datetime


class UserBehavioralMemoryPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    disabled_categories: List[str]
    retention_policy_days: int
    auto_outdate_dormant_days: int
    auto_synthesis_enabled: bool
    updated_at: datetime


class UserBehavioralMemoryPreferenceUpdate(BaseModel):
    disabled_categories: Optional[List[str]] = None
    retention_policy_days: Optional[int] = Field(None, ge=7, le=3650)
    auto_outdate_dormant_days: Optional[int] = Field(None, ge=7, le=365)
    auto_synthesis_enabled: Optional[bool] = None


class BehavioralMemoryOverviewRead(BaseModel):
    total_memories: int
    active_patterns_count: int
    emerging_patterns_count: int
    strengthening_patterns_count: int
    weakening_patterns_count: int
    outdated_patterns_count: int
    contradicted_patterns_count: int
    explicit_instructions_count: int
    user_corrected_count: int
    category_counts: Dict[str, int]
    source_type_counts: Dict[str, int]
    status_counts: Dict[str, int]
    primary_profile_status: Optional[str] = None
    primary_profile_confidence: Optional[float] = None
    recent_memories: List[BehavioralMemoryRead]
    recent_evolutions: List[Dict[str, Any]]


class MemorySynthesisResponse(BaseModel):
    created_memories_count: int
    reinforced_memories_count: int
    weakened_memories_count: int
    outdated_memories_count: int
    total_active_memories: int
    synthesis_messages: List[str]
