"""
Pydantic schemas for ContextIQ Knowledge-Grounded Conversational Assistant (Phase 8.8).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """Specific verifiable datum supporting an assistant statement."""
    entity_type: str = Field(..., description="Type of entity: TASK, PROJECT, GOAL, DEPENDENCY, BEHAVIORAL_MEMORY, BEHAVIORAL_TREND, RECOMMENDATION, PREDICTION")
    entity_id: str = Field(..., description="Unique ID of the entity")
    entity_title: str = Field(..., description="Title or summary of the entity")
    evidence_snippet: str = Field(..., description="Concrete fact, timestamp, or metric value")
    timestamp: Optional[str] = Field(None, description="Observation or update timestamp ISO string")
    confidence_or_metric: Optional[str] = Field(None, description="Confidence score, metric value, or status")

    model_config = ConfigDict(from_attributes=True)


class EntityReference(BaseModel):
    """Direct linkable entity mentioned in the response."""
    entity_type: str
    entity_id: str
    title: str
    status: Optional[str] = None
    url_or_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ActionProposal(BaseModel):
    """
    Governed workflow or action proposed by the assistant.
    Separates suggestion from mutation: always requires explicit user approval via Phase 7 governance.
    """
    action_identifier: str = Field(..., description="Registered action contract, e.g. task:defer_task, task:update_priority")
    target_entity_id: Optional[str] = Field(None, description="Target entity ID to be modified upon approval")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters required for action execution")
    rationale: str = Field(..., description="Data-driven reason for proposing this action")
    requires_governed_approval: bool = Field(True, description="Strictly True: LLM cannot auto-mutate state")
    governance_status: str = Field("PROPOSED", description="PROPOSED | AWAITING_APPROVAL")

    model_config = ConfigDict(from_attributes=True)


class StructuredAssistantResponse(BaseModel):
    """
    Rigorous evidence-grounded response payload for user productivity queries.
    Guarantees:
    - Direct, concise answer.
    - Explicit supporting evidence with timestamps.
    - Linked real-world entities.
    - Explicit uncertainty and missing data disclosure.
    - Governed action separation.
    """
    direct_answer: str = Field(..., description="Direct answer grounded strictly in verified user data")
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list, description="Verifiable facts backing the answer")
    relevant_entities: List[EntityReference] = Field(default_factory=list, description="Referenced tasks, projects, goals, etc.")
    data_timestamps: Dict[str, Optional[str]] = Field(default_factory=dict, description="Freshness timestamps of evaluated sources")
    uncertainty_level: Literal["LOW", "MEDIUM", "HIGH", "UNCERTAIN"] = Field("LOW", description="Epistemic uncertainty level")
    uncertainty_notes: Optional[str] = Field(None, description="Explanation for any uncertainty or data gaps")
    missing_information: List[str] = Field(default_factory=list, description="Explicit declaration of missing or unobserved data")
    suggested_next_steps: List[str] = Field(default_factory=list, description="Recommended next actions or follow-up questions")
    action_proposals: List[ActionProposal] = Field(default_factory=list, description="Proposed governed workflow actions (never auto-executed)")
    epistemic_disclaimer: Optional[str] = Field(
        "ContextIQ assistant answers are strictly grounded in your tracked tasks, projects, goals, and behavioral metrics. Unsupported claims are withheld.",
        description="Non-hallucination and epistemic boundary notice"
    )

    model_config = ConfigDict(from_attributes=True)


class AskAssistantRequest(BaseModel):
    """Input payload for user questions."""
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language question from user")
    conversation_id: Optional[uuid.UUID] = Field(None, description="Existing session ID, or None to start a new one")
    include_evidence: bool = Field(True, description="Whether to include supporting evidence details")
    include_proposals: bool = Field(True, description="Whether to include governed action proposals")


class AssistantMessageRead(BaseModel):
    """Read schema for a turn in the conversation."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    structured_response: Optional[StructuredAssistantResponse] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssistantConversationRead(BaseModel):
    """Read schema for conversation summary and history."""
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    recent_messages: List[AssistantMessageRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AssistantConversationListResponse(BaseModel):
    """List response for active user conversations."""
    conversations: List[AssistantConversationRead]
    total: int
