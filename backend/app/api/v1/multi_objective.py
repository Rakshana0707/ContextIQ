"""
Multi-Objective Intervention Optimization REST API Endpoints (ContextIQ Phase 6.7).

Exposes:
- Quantitative objectives and constraint catalogs.
- Multi-attribute utility optimization with Pareto-frontier evaluation.
- User customization preferences for objective weights and opt-outs.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.counterfactual import CandidateIntervention
from app.schemas.multi_objective_optimization import (
    MultiObjectiveOptimizationRequest,
    MultiObjectiveOptimizationResponse,
    ObjectiveWeights,
    UserOptimizationPreferences,
)
from app.services.multi_objective_service import MultiObjectiveService

router = APIRouter(prefix="/optimization", tags=["intervention-optimization"])


@router.get("/objectives", summary="List supported multi-objective dimensions")
def list_optimization_objectives() -> List[Dict[str, Any]]:
    """Returns the 8 optimization objectives with direction, descriptions, and baseline weights."""
    return MultiObjectiveService.list_objectives()


@router.get("/constraints", summary="List non-bypassable hard constraints")
def list_optimization_constraints() -> List[Dict[str, Any]]:
    """Returns the 7 non-bypassable hard constraints and gating rules."""
    return MultiObjectiveService.list_constraints()


@router.post(
    "/optimize",
    response_model=MultiObjectiveOptimizationResponse,
    summary="Execute multi-objective intervention optimization",
)
def optimize_intervention(
    request: MultiObjectiveOptimizationRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> MultiObjectiveOptimizationResponse:
    """
    Evaluates candidate interventions across 8 normalized objectives and 7 hard constraints.
    Computes Pareto-frontier and selects optimal action with No-Action safeguards.
    """
    if request.user_id is None:
        request.user_id = user_id
    return MultiObjectiveService.optimize_intervention(db=db, request=request)


@router.get(
    "/optimize",
    response_model=MultiObjectiveOptimizationResponse,
    summary="Execute multi-objective optimization (GET convenience)",
)
def optimize_intervention_get(
    task_id: Optional[uuid.UUID] = Query(default=None, description="Active Task ID if applicable"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> MultiObjectiveOptimizationResponse:
    """
    Convenience GET endpoint to obtain optimal intervention recommendation for current context.
    """
    req = MultiObjectiveOptimizationRequest(
        user_id=user_id,
        task_id=task_id,
    )
    return MultiObjectiveService.optimize_intervention(db=db, request=req)


@router.get(
    "/preferences",
    response_model=UserOptimizationPreferences,
    summary="Retrieve user optimization weights and preferences",
)
def get_user_optimization_preferences(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> UserOptimizationPreferences:
    """Retrieves user's explicit objective weights, notification quotas, and opt-outs."""
    return MultiObjectiveService.get_user_preferences(user_id=user_id)


@router.put(
    "/preferences",
    response_model=UserOptimizationPreferences,
    summary="Update user optimization weights and preferences",
)
def update_user_optimization_preferences(
    preferences: UserOptimizationPreferences,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> UserOptimizationPreferences:
    """Updates user's custom objective weights and intervention opt-out list."""
    preferences.user_id = user_id
    return MultiObjectiveService.update_user_preferences(preferences=preferences)
