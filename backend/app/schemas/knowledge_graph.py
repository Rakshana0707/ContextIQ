"""
Pydantic Schemas for ContextIQ Unified Productivity Knowledge Graph (Phase 8.1).
Defines schemas for nodes, edges, domain entities, provenance contracts, and reusable query operations.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import GraphNodeType, GraphRelationshipType, KnowledgeEvidenceSource


# ===========================================================================
# Node Schemas
# ===========================================================================

class KnowledgeNodeBase(BaseModel):
    node_type: GraphNodeType
    name: str = Field(..., max_length=255)
    entity_id: uuid.UUID
    entity_table: str = Field(..., max_length=64)
    properties: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeNodeCreate(KnowledgeNodeBase):
    pass


class KnowledgeNodeRead(KnowledgeNodeBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Edge & Relationship Contract Schemas
# ===========================================================================

class KnowledgeEdgeBase(BaseModel):
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relationship_type: GraphRelationshipType
    evidence_source: KnowledgeEvidenceSource = KnowledgeEvidenceSource.EXPLICIT_USER
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_inferred: bool = False
    weight: float = Field(default=1.0, ge=0.0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    provenance_payload: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_relationship_contract(self) -> KnowledgeEdgeBase:
        """
        Enforce strict epistemic boundary:
        - Inferred relationships cannot have 1.0 confidence or be presented as facts without evidence.
        - Ground truth facts (EXPLICIT_USER) cannot be marked as inferred.
        - Inferred relationships must have an inferred evidence source (ML, STATISTICAL, LLM).
        """
        if not self.is_inferred:
            if self.evidence_source in (
                KnowledgeEvidenceSource.ML_PREDICTION,
                KnowledgeEvidenceSource.LLM_HYPOTHESIS,
                KnowledgeEvidenceSource.STATISTICAL_ANALYSIS,
            ):
                raise ValueError(
                    f"Relationship from evidence source {self.evidence_source} must be flagged as is_inferred=True."
                )
            if self.confidence < 1.0:
                raise ValueError("Observed ground-truth relationships must have confidence=1.0.")
        else:
            if self.evidence_source == KnowledgeEvidenceSource.EXPLICIT_USER:
                raise ValueError("Explicit user relationships cannot be marked as is_inferred=True.")
            if self.confidence >= 1.0:
                raise ValueError("Inferred relationships cannot claim absolute certainty (confidence < 1.0 required).")
        return self


class KnowledgeEdgeCreate(KnowledgeEdgeBase):
    pass


class KnowledgeEdgeRead(KnowledgeEdgeBase):
    id: uuid.UUID
    user_id: uuid.UUID
    source_entity_id: Optional[uuid.UUID] = None
    target_entity_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Extended Domain Entity Schemas
# ===========================================================================

class ProjectBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    status: str = "ACTIVE"
    priority: str = "MEDIUM"
    target_completion_date: Optional[datetime] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoalBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: str = "PRODUCTIVITY"
    status: str = "ACTIVE"
    target_date: Optional[datetime] = None
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class GoalCreate(GoalBase):
    pass


class GoalRead(GoalBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MilestoneBase(BaseModel):
    title: str = Field(..., max_length=255)
    project_id: Optional[uuid.UUID] = None
    goal_id: Optional[uuid.UUID] = None
    due_date: Optional[datetime] = None
    status: str = "PENDING"
    order_index: int = 0
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneRead(MilestoneBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HabitBase(BaseModel):
    title: str = Field(..., max_length=255)
    cadence: str = "DAILY"
    target_frequency_per_week: int = 7
    streak_count: int = 0
    preferred_time_window: Optional[str] = None
    status: str = "ACTIVE"
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class HabitCreate(HabitBase):
    pass


class HabitRead(HabitBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BehavioralPatternBase(BaseModel):
    name: str = Field(..., max_length=128)
    pattern_category: str = "FRICTION"
    description: str
    frequency_per_week: float = 0.0
    friction_impact: float = 0.0
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    empirical_metrics: Dict[str, Any] = Field(default_factory=dict)
    discovered_at: Optional[datetime] = None


class BehavioralPatternCreate(BehavioralPatternBase):
    pass


class BehavioralPatternRead(BehavioralPatternBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionBase(BaseModel):
    decision_type: str = Field(..., max_length=64)
    chosen_option: str = Field(..., max_length=255)
    alternative_options: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    decided_at: Optional[datetime] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class DecisionCreate(DecisionBase):
    pass


class DecisionRead(DecisionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutcomeBase(BaseModel):
    outcome_type: str = Field(..., max_length=64)
    title: str = Field(..., max_length=255)
    metric_impact: Dict[str, Any] = Field(default_factory=dict)
    achieved_at: Optional[datetime] = None
    summary: Optional[str] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class OutcomeCreate(OutcomeBase):
    pass


class OutcomeRead(OutcomeBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceBase(BaseModel):
    title: str = Field(..., max_length=255)
    resource_type: str = "DOCUMENT"
    uri_or_path: str = Field(..., max_length=1024)
    description: Optional[str] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class ResourceCreate(ResourceBase):
    pass


class ResourceRead(ResourceBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Reusable Query Operation Request & Response Schemas
# ===========================================================================

class RelatedTaskItem(BaseModel):
    task_id: uuid.UUID
    title: str
    relationship_type: GraphRelationshipType
    confidence: float
    is_inferred: bool
    evidence_source: KnowledgeEvidenceSource
    status: str
    priority: str


class RelatedTasksResponse(BaseModel):
    task_id: uuid.UUID
    task_title: str
    related_tasks: List[RelatedTaskItem]
    total_count: int


class DependencyNodeItem(BaseModel):
    entity_id: uuid.UUID
    node_type: GraphNodeType
    name: str
    depth: int
    relationship_type: GraphRelationshipType
    is_blocking: bool
    status: str


class ProjectDependenciesResponse(BaseModel):
    project_id: uuid.UUID
    project_title: str
    dependencies: List[DependencyNodeItem]
    is_blocked: bool
    blocking_count: int


class AffectedGoalItem(BaseModel):
    goal_id: uuid.UUID
    goal_title: str
    category: str
    impact_path: List[str]
    delay_risk_score: float
    unfinished_task_count: int


class GoalsAffectedResponse(BaseModel):
    unfinished_task_id: uuid.UUID
    task_title: str
    affected_goals: List[AffectedGoalItem]
    total_affected: int


class EvidenceTrailItem(BaseModel):
    step: int
    source_type: GraphNodeType
    source_name: str
    relationship: GraphRelationshipType
    target_type: GraphNodeType
    target_name: str
    confidence: float
    is_inferred: bool
    evidence_source: KnowledgeEvidenceSource
    details: Dict[str, Any]


class RecommendationTraceResponse(BaseModel):
    recommendation_id: uuid.UUID
    recommendation_title: str
    recommendation_type: str
    evidence_trail: List[EvidenceTrailItem]
    primary_evidence_source: KnowledgeEvidenceSource
    overall_confidence: float
    has_inferred_steps: bool


class RecurringPatternItem(BaseModel):
    pattern_id: uuid.UUID
    name: str
    category: str
    description: str
    frequency_per_week: float
    friction_impact: float
    confidence: float
    associated_entities: List[str]


class RecurringBehavioralPatternsResponse(BaseModel):
    user_id: uuid.UUID
    patterns: List[RecurringPatternItem]
    total_patterns: int
    high_friction_count: int


class OutcomeDecisionTraceResponse(BaseModel):
    outcome_id: uuid.UUID
    outcome_title: str
    outcome_type: str
    metric_impact: Dict[str, Any]
    decision_trail: List[Dict[str, Any]]
    workflow_id: Optional[uuid.UUID] = None
    attribution_confidence: float
