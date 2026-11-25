"""
Pydantic v2 schemas for ContextIQ Contextual Bandit Engine adapter (Phase 4.6).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class BanditAlgorithm(str, Enum):
    LIN_UCB = "LIN_UCB"
    THOMPSON_SAMPLING = "THOMPSON_SAMPLING"
    UNIFORM_RANDOM = "UNIFORM_RANDOM"


class BanditSelectRequest(BaseModel):
    as_of: Optional[datetime] = None
    task_id: Optional[uuid.UUID] = None
    context_tag: Optional[str] = None
    quiet_hours_override: Optional[bool] = None
    excluded_arms: Optional[List[str]] = Field(default_factory=list)
    algorithm_override: Optional[BanditAlgorithm] = None
    active_hour_override: Optional[int] = Field(None, ge=0, le=23)


class BanditSelectResponse(ORMBase):
    decision_id: uuid.UUID
    user_id: uuid.UUID
    selected_arm: str
    is_no_action: bool
    algorithm: str
    policy_version: str
    predicted_expected_reward: float
    exploration_bonus: float
    propensity_score: float
    eligible_arms: List[str]
    context_summary: Dict[str, Any] = Field(default_factory=dict)
    decision_timestamp: datetime
    observation_window_end: datetime


class BanditFeedbackRequest(BaseModel):
    decision_id: uuid.UUID
    action: str = Field(
        ...,
        description="ACCEPTED, DISMISSED, SNOOZED, EXPLICIT_NEGATIVE, EXPIRED, NOOP_OBSERVED",
    )
    feedback_note: Optional[str] = None
    response_latency_seconds: Optional[float] = None
    task_completed: Optional[bool] = None
    resumption_lag_seconds: Optional[float] = None
    friction_index_after: Optional[float] = None
    subsequent_interruptions_count: Optional[int] = None


class BanditFeedbackResponse(ORMBase):
    decision_id: uuid.UUID
    arm_id: str
    explicit_reward: float
    behavioral_reward: float
    composite_reward: float
    updated_pull_count: int
    quarantined: bool
    attributed_at: datetime


class ArmMetrics(BaseModel):
    arm_id: str
    pull_count: int
    cumulative_reward: float
    mean_reward: float
    is_quarantined: bool
    consecutive_negative_rewards: int
    last_pulled_at: Optional[datetime] = None


class BanditMetricsResponse(BaseModel):
    user_id: uuid.UUID
    algorithm: str
    total_decisions: int
    total_feedback_events: int
    global_mean_reward: float
    no_action_rate: float
    arm_metrics: List[ArmMetrics]


class BanditPolicyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    algorithm: str
    exploration_alpha: float
    feature_dimension: int
    model_version: str
    rate_limit_minutes: int
    quiet_hours: List[int]
    quarantine_threshold: int
    quarantine_duration_hours: int
    all_registered_arms: List[str]
