"""
Task Ranking Schemas adapter for Adaptive Intelligence module (Phase 4.4).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.profile_schemas import ORMBase


class RankingPreset(str, Enum):
    BALANCED = "BALANCED"
    DEEP_WORK = "DEEP_WORK"
    DEADLINE_CRUNCH = "DEADLINE_CRUNCH"
    RECOVERY_MODE = "RECOVERY_MODE"


class RankingWeightConfig(BaseModel):
    urgency_weight: float = Field(0.30, ge=0.0, le=1.0)
    forgetting_risk_weight: float = Field(0.25, ge=0.0, le=1.0)
    personal_suitability_weight: float = Field(0.20, ge=0.0, le=1.0)
    context_compatibility_weight: float = Field(0.15, ge=0.0, le=1.0)
    scheduling_feasibility_weight: float = Field(0.10, ge=0.0, le=1.0)

    @classmethod
    def for_preset(cls, preset: RankingPreset | str) -> "RankingWeightConfig":
        p = (preset.value if hasattr(preset, "value") else str(preset)).upper()
        if "DEEP_WORK" in p:
            return cls(
                urgency_weight=0.15,
                forgetting_risk_weight=0.15,
                personal_suitability_weight=0.40,
                context_compatibility_weight=0.15,
                scheduling_feasibility_weight=0.15,
            )
        elif "DEADLINE_CRUNCH" in p:
            return cls(
                urgency_weight=0.55,
                forgetting_risk_weight=0.15,
                personal_suitability_weight=0.10,
                context_compatibility_weight=0.10,
                scheduling_feasibility_weight=0.10,
            )
        elif "RECOVERY_MODE" in p:
            return cls(
                urgency_weight=0.15,
                forgetting_risk_weight=0.15,
                personal_suitability_weight=0.35,
                context_compatibility_weight=0.20,
                scheduling_feasibility_weight=0.15,
            )
        return cls(
            urgency_weight=0.30,
            forgetting_risk_weight=0.25,
            personal_suitability_weight=0.20,
            context_compatibility_weight=0.15,
            scheduling_feasibility_weight=0.10,
        )

    def normalized(self) -> "RankingWeightConfig":
        total = (
            self.urgency_weight
            + self.forgetting_risk_weight
            + self.personal_suitability_weight
            + self.context_compatibility_weight
            + self.scheduling_feasibility_weight
        )
        if total <= 0:
            return RankingWeightConfig()
        return RankingWeightConfig(
            urgency_weight=round(self.urgency_weight / total, 3),
            forgetting_risk_weight=round(self.forgetting_risk_weight / total, 3),
            personal_suitability_weight=round(self.personal_suitability_weight / total, 3),
            context_compatibility_weight=round(self.context_compatibility_weight / total, 3),
            scheduling_feasibility_weight=round(self.scheduling_feasibility_weight / total, 3),
        )


class ScoreBreakdown(BaseModel):
    urgency_score: float = Field(..., ge=0.0, le=1.0)
    forgetting_risk_score: float = Field(..., ge=0.0, le=1.0)
    personal_suitability_score: float = Field(..., ge=0.0, le=1.0)
    context_compatibility_score: float = Field(..., ge=0.0, le=1.0)
    scheduling_feasibility_score: float = Field(..., ge=0.0, le=1.0)


class RecommendedFocusWindow(BaseModel):
    start_time: str
    end_time: str
    quality_score: float
    task_category: Optional[str] = None
    reason: str


class RankedTaskItem(BaseModel):
    task_id: uuid.UUID
    title: str
    context_tag: Optional[str] = None
    priority: str
    status: str
    due_at: Optional[datetime] = None
    estimated_minutes: int
    recovery_buffer_minutes: int = 0
    rank: int
    composite_score: float = Field(..., ge=0.0, le=100.0)
    primary_driver: str
    score_breakdown: ScoreBreakdown
    grounded_explanation: str
    recommended_focus_window: Optional[RecommendedFocusWindow] = None
    constraints_applied: List[str] = Field(default_factory=list)
    is_blocked: bool = False
    blocked_by_task_id: Optional[uuid.UUID] = None
    data_sufficiency: str = "ESTABLISHED"
    user_pinned: bool = False


class TaskRankingResponse(BaseModel):
    user_id: uuid.UUID
    generated_at: datetime
    reference_time: datetime
    preset_applied: str
    current_context: Dict[str, Any] = Field(default_factory=dict)
    items: List[RankedTaskItem]
    summary_insights: List[str] = Field(default_factory=list)


class TaskRankingPreviewRequest(BaseModel):
    as_of: Optional[datetime] = None
    current_context_tag: Optional[str] = None
    current_location_id: Optional[uuid.UUID] = None
    preset: Optional[RankingPreset] = RankingPreset.BALANCED
    custom_weights: Optional[RankingWeightConfig] = None
    include_blocked: bool = True
    active_hour: Optional[int] = None


class TaskRankingFeedbackCreate(BaseModel):
    task_id: uuid.UUID
    action: str
    rank_position: int
    composite_score: float
    feedback_note: Optional[str] = None


class TaskRankingFeedbackRead(ORMBase):
    id: uuid.UUID
    task_id: uuid.UUID
    action: str
    rank_position: int
    composite_score: float
    feedback_note: Optional[str] = None
    created_at: datetime
