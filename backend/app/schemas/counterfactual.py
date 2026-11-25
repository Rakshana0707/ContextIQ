"""
Counterfactual Recommendation and Intervention Analysis Schemas (ContextIQ Phase 6.4).

Defines:
- Candidate intervention alternatives (No intervention, Immediate reminder, Delayed reminder,
  Calendar rescheduling, Recovery buffer, Focus session).
- Fine-grained lifecycle demarcation: Recommended, Delivered, Accepted, Dismissed, Executed.
- Multi-dimensional potential outcomes: Resumption, Completion, Recovery duration, Friction, Burden.
- Counterfactual meta-learner architectures: T-Learner, S-Learner, X-Learner, Doubly Robust Learner.
- Data coverage tiers, uncertainty intervals, and deterministic fallback criteria.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class CandidateIntervention(str, Enum):
    NO_INTERVENTION = "no_intervention"
    IMMEDIATE_REMINDER = "immediate_reminder"
    DELAYED_REMINDER = "delayed_reminder"
    CALENDAR_RESCHEDULING = "calendar_rescheduling"
    SHORT_RECOVERY_BUFFER = "short_recovery_buffer"
    FOCUS_SESSION_RECOMMENDATION = "focus_session_recommendation"
    BREAK_LARGE_TASK = "break_large_task"


class InterventionLifecycleStage(str, Enum):
    RECOMMENDED = "recommended"  # System generated candidate
    DELIVERED = "delivered"      # Presented to user in UI
    ACCEPTED = "accepted"        # Explicitly accepted/clicked by user
    DISMISSED = "dismissed"      # Explicitly dismissed or ignored
    EXECUTED = "executed"        # Empirically verified behavioral execution in telemetry


class DataCoverageTier(str, Enum):
    STRONG = "strong"            # N >= 40, overlap >= 0.70 (Tight confidence bounds)
    MODERATE = "moderate"        # 20 <= N < 40, overlap >= 0.50 (Standard bounds)
    SPARSE = "sparse"            # 10 <= N < 20, overlap >= 0.30 (Widened conformal bounds)
    UNSUPPORTED = "unsupported"  # N < 10 or severe lack of overlap (Excluded from ranking)


class CounterfactualLearnerType(str, Enum):
    T_LEARNER = "t_learner"
    S_LEARNER = "s_learner"
    X_LEARNER = "x_learner"
    DOUBLY_ROBUST_LEARNER = "doubly_robust_learner"


class RecommendationStrategy(str, Enum):
    COUNTERFACTUAL_OPTIMIZED = "counterfactual_optimized"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class PotentialOutcomeVector(BaseModel):
    """Potential outcomes Y(a) under a specific intervention strategy a."""
    task_resumption_probability: float = Field(
        ..., ge=0.0, le=1.0, description="P(Resumed within 15m | a)"
    )
    task_completion_probability: float = Field(
        ..., ge=0.0, le=1.0, description="P(Completed on time | a)"
    )
    expected_recovery_duration_seconds: float = Field(
        ..., ge=0.0, description="Expected cognitive recovery duration in seconds (30m horizon)"
    )
    expected_behavioral_friction: float = Field(
        ..., ge=0.0, le=100.0, description="Prospective Behavioral Friction Index BFI (0-100, 30m horizon)"
    )
    expected_notification_burden: float = Field(
        ..., ge=0.0, le=1.0, description="Psychological burden and disruption penalty (5m horizon)"
    )


class IncrementalBenefitVector(BaseModel):
    """Incremental counterfactual lift delta = Y(a) - Y(a_0) relative to No Intervention."""
    resumption_lift_pct: float = Field(..., description="Delta resumption probability percentage")
    completion_lift_pct: float = Field(..., description="Delta completion probability percentage")
    recovery_time_saved_seconds: float = Field(..., description="Seconds saved in recovery (positive = faster)")
    friction_reduction_points: float = Field(..., description="BFI points reduced (positive = lower friction)")
    burden_penalty: float = Field(..., description="Notification burden cost (negative = disruption penalty)")


class CounterfactualCandidateResult(BaseModel):
    candidate: CandidateIntervention = Field(..., description="Candidate intervention identifier")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Strategy explanation")
    category: str = Field(..., description="FOCUS, RECOVERY, TASK, CONTEXTUAL")
    is_supported: bool = Field(..., description="True if evidence & overlap support estimation")
    coverage_tier: DataCoverageTier = Field(..., description="Data coverage classification")
    exclusion_reason: Optional[str] = Field(None, description="Reason if unsupported or excluded")

    potential_outcomes: Optional[PotentialOutcomeVector] = Field(
        None, description="Predicted multi-dimensional potential outcomes"
    )
    incremental_benefit: Optional[IncrementalBenefitVector] = Field(
        None, description="Estimated incremental lift over No Intervention"
    )
    composite_uplift_score: Optional[float] = Field(
        None, description="Multi-objective composite utility score (-100 to 100)"
    )

    # Uncertainty intervals for potential outcomes: Dict of feature -> (lower, upper)
    uncertainty_intervals: Optional[Dict[str, Tuple[float, float]]] = Field(
        None, description="90% conformal / asymptotic uncertainty intervals"
    )

    empirical_sample_size: int = Field(..., description="Historical observations of this intervention")
    empirical_execution_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Historical execution-given-delivery rate"
    )
    overlap_score: float = Field(
        ..., ge=0.0, le=1.0, description="Propensity common support overlap score"
    )
    learner_used: CounterfactualLearnerType = Field(
        default=CounterfactualLearnerType.DOUBLY_ROBUST_LEARNER,
        description="Meta-learner used for estimation",
    )
    assumptions: List[str] = Field(default_factory=list, description="Explicit causal assumptions")


class CounterfactualComparisonRequest(BaseModel):
    task_id: Optional[uuid.UUID] = Field(None, description="Target task if evaluating task context")
    user_id: Optional[uuid.UUID] = Field(None, description="Target user UUID")
    learner: CounterfactualLearnerType = Field(
        default=CounterfactualLearnerType.DOUBLY_ROBUST_LEARNER,
        description="Meta-learner for potential outcome estimation",
    )
    context_features: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Point-in-time contextual features at decision timestamp"
    )
    strict_uncertainty_threshold: float = Field(
        default=0.35, description="Max allowed interval width to permit counterfactual override"
    )


class CounterfactualComparisonResponse(BaseModel):
    context_id: str = Field(..., description="Unique evaluation session ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    evaluation_timestamp: datetime = Field(..., description="Timestamp of counterfactual comparison")
    target_task_id: Optional[uuid.UUID] = Field(None, description="Evaluated task if applicable")

    baseline_candidate: CandidateIntervention = Field(
        default=CandidateIntervention.NO_INTERVENTION, description="Control baseline"
    )
    candidates: List[CounterfactualCandidateResult] = Field(
        ..., description="Full list of evaluated candidate alternatives"
    )

    recommended_champion: Optional[CandidateIntervention] = Field(
        None, description="Top-ranked intervention candidate"
    )
    recommendation_source: RecommendationStrategy = Field(
        ..., description="COUNTERFACTUAL_OPTIMIZED or DETERMINISTIC_FALLBACK"
    )
    fallback_reason: Optional[str] = Field(
        None, description="Reason why deterministic fallback was used if applicable"
    )

    disclaimer: str = Field(
        default=(
            "COUNTERFACTUAL POTENTIAL OUTCOMES ARE MODELED ESTIMATES, NOT OBSERVED HISTORICAL FACTS. "
            "Estimates represent conditional expectations E[Y(a)|X] valid strictly under exchangeability "
            "and positivity assumptions. Unsupported options are explicitly excluded from decisioning."
        ),
        description="Scientific integrity disclaimer",
    )
