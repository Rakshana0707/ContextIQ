"""
REST API endpoints for Long-Term Behavioral Memory & Pattern Evolution (Phase 8.3).
Provides authenticated routes for memory inspection, pattern synthesis, temporal summaries,
and user correction / control.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.behavioral_memory import (
    MemoryCategory,
    MemorySourceType,
    MemoryValidityStatus,
)
from app.schemas.behavioral_memory import (
    BehavioralMemoryCreate,
    BehavioralMemoryOverviewRead,
    BehavioralMemoryRead,
    BehavioralMemoryUpdate,
    BehavioralTemporalSummaryRead,
    MemoryCorrectionRequest,
    MemorySynthesisResponse,
    UserBehavioralMemoryPreferenceRead,
    UserBehavioralMemoryPreferenceUpdate,
)
from app.services.behavioral_memory_service import BehavioralMemoryService

router = APIRouter(prefix="/memory", tags=["behavioral-memory"])


@router.get("/overview", response_model=BehavioralMemoryOverviewRead)
def get_memory_overview(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns a unified behavioral memory overview across categories, evolution stages, and profile baselines."""
    return BehavioralMemoryService.get_memory_overview(db=db, user_id=user_id)


@router.get("", response_model=List[BehavioralMemoryRead])
def list_memories(
    category: Optional[MemoryCategory] = Query(None, description="Filter by memory category"),
    validity_status: Optional[MemoryValidityStatus] = Query(None, description="Filter by validity status"),
    source_type: Optional[MemorySourceType] = Query(None, description="Filter by source type"),
    q: Optional[str] = Query(None, description="Search query against title or description"),
    include_disabled: bool = Query(False, description="Whether to include user-disabled memories"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves stored behavioral memories for the authenticated user."""
    memories = BehavioralMemoryService.list_memories(
        db=db,
        user_id=user_id,
        category=category,
        validity_status=validity_status,
        source_type=source_type,
        search_query=q,
        include_disabled=include_disabled,
        limit=limit,
        offset=offset,
    )
    return [BehavioralMemoryRead.model_validate(m) for m in memories]


@router.post("", response_model=BehavioralMemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: BehavioralMemoryCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Explicitly records a new behavioral memory or user directive."""
    memory = BehavioralMemoryService.create_memory(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(memory)
    return BehavioralMemoryRead.model_validate(memory)


@router.post("/synthesize", response_model=MemorySynthesisResponse)
def synthesize_memories(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Triggers automated memory synthesis grounding the authoritative UserBehavioralProfile,
    Focus Windows, Interventions, and telemetry into long-term behavioral memory records.
    """
    res = BehavioralMemoryService.synthesize_memories_from_behavioral_profile(db=db, user_id=user_id)
    db.commit()
    return res


@router.get("/preferences", response_model=UserBehavioralMemoryPreferenceRead)
def get_memory_preferences(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns user memory preferences including disabled categories and retention settings."""
    pref = BehavioralMemoryService.get_or_create_preferences(db=db, user_id=user_id)
    return UserBehavioralMemoryPreferenceRead.model_validate(pref)


@router.patch("/preferences", response_model=UserBehavioralMemoryPreferenceRead)
def update_memory_preferences(
    payload: UserBehavioralMemoryPreferenceUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates user memory preferences, retention windows, or disabled categories."""
    pref = BehavioralMemoryService.update_preferences(db=db, user_id=user_id, payload=payload)
    db.commit()
    db.refresh(pref)
    return UserBehavioralMemoryPreferenceRead.model_validate(pref)


@router.get("/summaries", response_model=List[BehavioralTemporalSummaryRead])
def list_temporal_summaries(
    limit: int = Query(10, ge=1, le=50),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves weekly and monthly temporal summaries of pattern evolution."""
    summaries = BehavioralMemoryService.get_temporal_summaries(db=db, user_id=user_id, limit=limit)
    return [BehavioralTemporalSummaryRead.model_validate(s) for s in summaries]


@router.post("/summaries/generate", response_model=BehavioralTemporalSummaryRead, status_code=status.HTTP_201_CREATED)
def generate_temporal_summary(
    period_type: str = Query("WEEKLY", pattern="^(WEEKLY|MONTHLY)$"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Generates an on-demand temporal summary for the specified period."""
    summary = BehavioralMemoryService.generate_temporal_summary(db=db, user_id=user_id, period_type=period_type)
    db.commit()
    db.refresh(summary)
    return BehavioralTemporalSummaryRead.model_validate(summary)


@router.post("/reset")
def reset_memories(
    category: Optional[MemoryCategory] = Query(None, description="Optional category to selectively reset"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Resets all behavioral memories or memories within a designated category."""
    deleted_count = BehavioralMemoryService.reset_behavioral_memories(db=db, user_id=user_id, category=category)
    db.commit()
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "category": category.value if category else "ALL",
        "message": f"Successfully reset {deleted_count} behavioral memories.",
    }


@router.get("/{memory_id}", response_model=BehavioralMemoryRead)
def get_memory(
    memory_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Fetches details, supporting evidence, and evolution history for a specific memory."""
    memory = BehavioralMemoryService.get_memory_by_id(db=db, user_id=user_id, memory_id=memory_id)
    return BehavioralMemoryRead.model_validate(memory)


@router.patch("/{memory_id}", response_model=BehavioralMemoryRead)
def update_memory(
    memory_id: uuid.UUID,
    payload: BehavioralMemoryUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates memory attributes, active status, or user notes."""
    memory = BehavioralMemoryService.update_memory(db=db, user_id=user_id, memory_id=memory_id, payload=payload)
    db.commit()
    db.refresh(memory)
    return BehavioralMemoryRead.model_validate(memory)


@router.post("/{memory_id}/correct", response_model=BehavioralMemoryRead)
def correct_memory(
    memory_id: uuid.UUID,
    payload: MemoryCorrectionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """User-initiated correction of inaccurate or misinferred behavioral memories."""
    memory = BehavioralMemoryService.correct_memory(db=db, user_id=user_id, memory_id=memory_id, correction=payload)
    db.commit()
    db.refresh(memory)
    return BehavioralMemoryRead.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Deletes a behavioral memory record permanently."""
    BehavioralMemoryService.delete_memory(db=db, user_id=user_id, memory_id=memory_id)
    db.commit()
    return None
