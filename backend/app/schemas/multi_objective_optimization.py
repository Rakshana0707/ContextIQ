"""
Multi-Objective Intervention Optimization Schemas (ContextIQ Phase 6.7).

Defines:
- 8 Quantitative Optimization Objectives (Completion, Resumption, Recovery, Friction,
  Notification Economy, Interruption Comfort, User Preferences, Schedule Feasibility).
- 7 Non-Bypassable Hard Constraints (Quiet Hours, Max Notification Frequency,
  Calendar Availability, Working Hours, Task Constraints, Consent, Opt-Outs).
- Context-dependent dynamic weight adaptation rules.
- Multi-dimensional Pareto-front representations and dominance rankings.
- Explicit No-Action preference logic and transparent trade-off explanations.
- Safety boundaries: Proposal-only recommendations requiring user approval.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.schemas.counterfactual import CandidateIntervention


class OptimizationObjective(str, Enum):
    TASK_COMPLETION = "task_completion"                  # Higher is better: P(Completion on time)
    TASK_RESUMPTION = "task_resumption"                  # Higher is better: P(Resumption within 15m)
    RECOVERY_DURATION = "recovery_duration"              # Higher is better: Recovery speed / time saved
    BEHAVIORAL_FRICTION = "behavioral_friction"          # Higher is better: Friction reduction (100 - BFI)
    NOTIFICATION_ECONOMY = "notification_economy"        # Higher is better: Low notification disruption (1 - Burden)
    INTERRUPTION_COMFORT = "interruption_comfort"        # Higher is better: Preservation of cognitive focus
    USER_PREFERENCES = "user_preferences"                # Higher is better: Alignment with explicit settings
    SCHEDULE_FEASIBILITY = "schedule_feasibility"        # Higher is better: Calendar slack / fit without conflict


class HardConstraintType(str, Enum):
    QUIET_HOURS = "quiet_hours"                          # Suppresses notification alerts during quiet window
    MAX_NOTIFICATION_FREQUENCY = "max_notification_freq" # Enforces hourly and daily notification quotas
    CALENDAR_AVAILABILITY = "calendar_availability"      # Prohibits placing tasks in busy calendar blocks
    WORKING_HOURS = "working_hours"                      # Restricts scheduled events to user working hours
    EXPLICIT_TASK_CONSTRAINTS = "task_constraints"       # Respects immutability flags and hard deadlines
    CONSENT_AND_PERMISSIONS = "consent_permissions"      # Validates user consent and channel permissions
    USER_OPT_OUT = "user_opt_out"                        # Respects explicit user opt-outs per intervention type


class OptimizationConstraintStatus(BaseModel):
    constraint_type: HardConstraintType = Field(..., description="Type of hard constraint checked")
    passed: bool = Field(..., description="True if constraint is satisfied, False if violated")
    reason: Optional[str] = Field(None, description="Detailed explanation if violated or passed")


class ObjectiveVector(BaseModel):
    """
    Normalized [0.0, 1.0] performance vector across all 8 objectives.
    All objectives are formatted so that HIGHER IS BETTER (1.0 = optimal, 0.0 = worst).
    """
    task_completion: float = Field(..., ge=0.0, le=1.0, description="P(Completion on time)")
    task_resumption: float = Field(..., ge=0.0, le=1.0, description="P(Resumption within 15m)")
    recovery_duration: float = Field(..., ge=0.0, le=1.0, description="Cognitive recovery score / speed")
    behavioral_friction: float = Field(..., ge=0.0, le=1.0, description="Friction reduction score (1 - BFI/100)")
    notification_economy: float = Field(..., ge=0.0, le=1.0, description="Notification economy (1 - Burden penalty)")
    interruption_comfort: float = Field(..., ge=0.0, le=1.0, description="Cognitive focus comfort")
    user_preferences: float = Field(..., ge=0.0, le=1.0, description="Affinity / explicit preference alignment")
    schedule_feasibility: float = Field(..., ge=0.0, le=1.0, description="Calendar buffer / schedule slack score")

    def to_dict(self) -> Dict[str, float]:
        return {
            "task_completion": self.task_completion,
            "task_resumption": self.task_resumption,
            "recovery_duration": self.recovery_duration,
            "behavioral_friction": self.behavioral_friction,
            "notification_economy": self.notification_economy,
            "interruption_comfort": self.interruption_comfort,
            "user_preferences": self.user_preferences,
            "schedule_feasibility": self.schedule_feasibility,
        }


class ObjectiveWeights(BaseModel):
    """
    Normalized non-negative weights for scalarized multi-attribute utility.
    Weights sum to 1.0.
    """
    task_completion: float = Field(default=0.20, ge=0.0, le=1.0)
    task_resumption: float = Field(default=0.15, ge=0.0, le=1.0)
    recovery_duration: float = Field(default=0.15, ge=0.0, le=1.0)
    behavioral_friction: float = Field(default=0.15, ge=0.0, le=1.0)
    notification_economy: float = Field(default=0.15, ge=0.0, le=1.0)
    interruption_comfort: float = Field(default=0.10, ge=0.0, le=1.0)
    user_preferences: float = Field(default=0.05, ge=0.0, le=1.0)
    schedule_feasibility: float = Field(default=0.05, ge=0.0, le=1.0)

    def normalized(self) -> ObjectiveWeights:
        """Returns normalized weights that strictly sum to 1.0."""
        total = (
            self.task_completion
            + self.task_resumption
            + self.recovery_duration
            + self.behavioral_friction
            + self.notification_economy
            + self.interruption_comfort
            + self.user_preferences
            + self.schedule_feasibility
        )
        if total <= 1e-6:
            # Default uniform
            return ObjectiveWeights(
                task_completion=0.125,
                task_resumption=0.125,
                recovery_duration=0.125,
                behavioral_friction=0.125,
                notification_economy=0.125,
                interruption_comfort=0.125,
                user_preferences=0.125,
                schedule_feasibility=0.125,
            )
        return ObjectiveWeights(
            task_completion=round(self.task_completion / total, 4),
            task_resumption=round(self.task_resumption / total, 4),
            recovery_duration=round(self.recovery_duration / total, 4),
            behavioral_friction=round(self.behavioral_friction / total, 4),
            notification_economy=round(self.notification_economy / total, 4),
            interruption_comfort=round(self.interruption_comfort / total, 4),
            user_preferences=round(self.user_preferences / total, 4),
            schedule_feasibility=round(self.schedule_feasibility / total, 4),
        )


class EvaluatedCandidate(BaseModel):
    """Detailed evaluation of an intervention candidate in objective and constraint space."""
    candidate: CandidateIntervention = Field(..., description="Candidate intervention identifier")
    title: str = Field(..., description="Human-readable title")
    is_feasible: bool = Field(..., description="True if satisfies all hard constraints")
    constraint_violations: List[str] = Field(default_factory=list, description="List of violated constraints")
    
    # Objective Performance
    objectives: ObjectiveVector = Field(..., description="Normalized 8-dimensional objective vector")
    weighted_utility: float = Field(..., description="Scalarized multi-attribute utility score in [0.0, 1.0]")
    net_utility_lift: float = Field(
        ..., description="Delta utility relative to No-Intervention: U(a) - U(No-Action)"
    )

    # Pareto-Front Metrics
    is_pareto_optimal: bool = Field(..., description="True if candidate is non-dominated on Pareto front")
    pareto_rank: int = Field(default=1, description="Pareto non-dominance rank (1 = frontier)")
    dominates: List[CandidateIntervention] = Field(default_factory=list, description="Candidates dominated by this option")
    dominated_by: List[CandidateIntervention] = Field(default_factory=list, description="Candidates that dominate this option")

    # Trade-off Analysis
    improved_objectives: List[str] = Field(default_factory=list, description="Objectives improved over No-Action")
    worsened_objectives: List[str] = Field(default_factory=list, description="Objectives worsened relative to No-Action (trade-offs)")

    # Uncertainty & Governance
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0, description="Estimation confidence score")
    uncertainty_width: float = Field(default=0.15, description="Average uncertainty interval width")


class MultiObjectiveOptimizationRequest(BaseModel):
    user_id: Optional[uuid.UUID] = Field(None, description="User UUID")
    task_id: Optional[uuid.UUID] = Field(None, description="Active Task UUID if applicable")
    current_time: Optional[datetime] = Field(None, description="Evaluation timestamp")
    context_features: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Point-in-time behavioral and cognitive context"
    )
    custom_weights: Optional[ObjectiveWeights] = Field(
        None, description="Custom user objective weights (overrides defaults)"
    )
    user_constraints: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Explicit constraint overrides or parameters"
    )
    strict_uncertainty_threshold: float = Field(
        default=0.35, ge=0.05, le=1.0, description="Max acceptable uncertainty width before falling back to No-Action"
    )
    min_utility_lift_threshold: float = Field(
        default=0.04, ge=0.0, le=0.5, description="Min delta utility over No-Action required to justify intervention"
    )


class MultiObjectiveOptimizationResponse(BaseModel):
    optimization_id: str = Field(..., description="Unique run identifier")
    user_id: uuid.UUID = Field(..., description="User UUID")
    evaluated_at: datetime = Field(..., description="Optimization timestamp")
    
    # Selected Decision
    selected_intervention: CandidateIntervention = Field(..., description="Optimal intervention candidate")
    is_no_action: bool = Field(..., description="True if No-Action was selected as optimal or safe fallback")
    selection_rationale: str = Field(..., description="Comprehensive explanation of selection decision")
    
    # Multi-Objective Balances
    effective_weights: ObjectiveWeights = Field(..., description="Weights used after context adaptation")
    context_adaptations: List[str] = Field(
        default_factory=list, description="Dynamic adjustments applied to weights based on real-time context"
    )
    
    # Candidate Space & Pareto Frontier
    pareto_frontier: List[EvaluatedCandidate] = Field(
        ..., description="Non-dominated candidates on the Pareto frontier"
    )
    all_evaluated_candidates: List[EvaluatedCandidate] = Field(
        ..., description="All evaluated candidates including dominated and filtered options"
    )
    
    # Constraints & Explanations
    applied_constraints: List[OptimizationConstraintStatus] = Field(
        ..., description="Audit of all non-bypassable hard constraints checked"
    )
    improved_objectives: List[str] = Field(
        default_factory=list, description="Objectives positively impacted by the selected intervention"
    )
    worsened_objectives: List[str] = Field(
        default_factory=list, description="Objectives with negative trade-offs compared to No-Action"
    )
    
    # Safety Boundaries
    requires_authorization: bool = Field(
        default=True,
        description="Safety flag: System generates proposals only; external execution requires authorization",
    )
    disclaimer: str = Field(
        default="Optimization balances productivity against cognitive burden and quiet hours. No-Action is preferred when benefit is negligible or uncertainty exceeds tolerance.",
        description="Scientific and ethical governance notice",
    )


class UserOptimizationPreferences(BaseModel):
    """User-configurable optimization weights and constraint preferences."""
    user_id: uuid.UUID
    preferred_weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    opted_out_interventions: List[CandidateIntervention] = Field(default_factory=list)
    max_daily_interventions: int = Field(default=8, ge=1, le=50)
    max_hourly_interventions: int = Field(default=2, ge=1, le=10)
    cooldown_minutes_between_interventions: int = Field(default=30, ge=5, le=180)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
