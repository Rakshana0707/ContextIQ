"""
Counterfactual Recommendation and Intervention Comparison API Endpoints (ContextIQ Phase 6.4).

Exposes:
- Candidate intervention catalog.
- Multi-treatment counterfactual comparison engine.
- Multi-objective potential outcome forecasting and uplift ranking.
- Fallback disclosures when data coverage or uncertainty violates guardrails.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.counterfactual import (
    CandidateIntervention,
    CounterfactualComparisonRequest,
    CounterfactualComparisonResponse,
    CounterfactualLearnerType,
)
from app.services.counterfactual_learners import CANDIDATE_CATALOG_METADATA
from app.services.counterfactual_service import CounterfactualService

router = APIRouter(prefix="/counterfactual", tags=["counterfactual"])


@router.get("/candidates", summary="List all supported candidate interventions")
def list_candidate_interventions() -> List[Dict[str, Any]]:
    """Returns catalog of supported intervention candidates and their categories."""
    return [
        {
            "candidate": cand.value,
            "title": meta["title"],
            "description": meta["description"],
            "category": meta["category"],
        }
        for cand, meta in CANDIDATE_CATALOG_METADATA.items()
    ]


@router.post(
    "/compare",
    response_model=CounterfactualComparisonResponse,
    summary="Compare intervention alternatives and estimate potential outcomes",
)
def compare_counterfactual_interventions(
    request: CounterfactualComparisonRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CounterfactualComparisonResponse:
    """
    Evaluates multi-treatment potential outcomes Y(a) across candidate interventions.
    Ranks supported options by incremental benefit over baseline and transparently
    falls back to deterministic logic if counterfactual data coverage is insufficient.
    """
    if request.user_id is None:
        request.user_id = user_id
    return CounterfactualService.compare_interventions(db=db, request=request)


@router.get(
    "/compare",
    response_model=CounterfactualComparisonResponse,
    summary="Compare intervention alternatives (GET convenience)",
)
def compare_counterfactual_interventions_get(
    task_id: Optional[uuid.UUID] = Query(None, description="Target task UUID if applicable"),
    learner: CounterfactualLearnerType = Query(
        default=CounterfactualLearnerType.DOUBLY_ROBUST_LEARNER,
        description="Meta-learner architecture",
    ),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CounterfactualComparisonResponse:
    """Convenience GET endpoint to evaluate candidate counterfactual outcomes."""
    req = CounterfactualComparisonRequest(
        task_id=task_id,
        user_id=user_id,
        learner=learner,
    )
    return CounterfactualService.compare_interventions(db=db, request=req)
