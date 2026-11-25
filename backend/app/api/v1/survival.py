"""
Dynamic Survival & Personalized Time-to-Event REST API Endpoints (ContextIQ Phase 6.6).

Exposes:
- Supported survival event targets and horizon metadata.
- Champion survival model benchmark across event families.
- Dynamic point-in-time survival curve predictions.
- Dynamic landmarking updates triggered by live behavioral events.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.dynamic_survival import (
    DynamicSurvivalPredictionRequest,
    DynamicSurvivalPredictionResponse,
    DynamicUpdateTrigger,
    SurvivalBenchmarkMetrics,
    SurvivalEventTarget,
)
from app.services.dynamic_survival_service import DynamicSurvivalService

router = APIRouter(prefix="/survival", tags=["survival-prediction"])


@router.get("/targets", summary="List supported dynamic survival event targets")
def list_survival_targets() -> List[Dict[str, Any]]:
    """
    Returns the 4 segregated time-to-event targets (Task Abandonment, Task Completion,
    Confirmed Task Resumption, Confirmed Recovery) with horizon definitions and censoring rules.
    """
    return DynamicSurvivalService.list_supported_targets()


@router.get(
    "/benchmark",
    response_model=List[SurvivalBenchmarkMetrics],
    summary="Benchmark survival architectures against non-parametric baseline",
)
def get_survival_benchmark(
    target: SurvivalEventTarget = Query(
        default=SurvivalEventTarget.TASK_ABANDONMENT,
        description="Target time-to-event outcome",
    ),
    force_rerun: bool = Query(default=False, description="Re-execute benchmark evaluation"),
) -> List[SurvivalBenchmarkMetrics]:
    """
    Evaluates candidate models (Log-Normal AFT, Weibull AFT, Cox PH, Kaplan-Meier)
    and reports C-index, Integrated Brier Score, and horizon-specific AUC.
    """
    return DynamicSurvivalService.get_or_run_benchmark(target=target, force_rerun=force_rerun)


@router.post(
    "/predict",
    response_model=DynamicSurvivalPredictionResponse,
    summary="Generate dynamic conditional survival prediction",
)
def predict_dynamic_survival(
    request: DynamicSurvivalPredictionRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DynamicSurvivalPredictionResponse:
    """
    Forecasts conditional survival curve S(t | T > t_curr) and median time-to-event.
    Applies empirical Bayes shrinkage and returns personalization tier.
    """
    if request.user_id is None:
        request.user_id = user_id
    return DynamicSurvivalService.predict_survival(db=db, request=request)


@router.get(
    "/predict",
    response_model=DynamicSurvivalPredictionResponse,
    summary="Generate dynamic survival prediction (GET convenience)",
)
def predict_dynamic_survival_get(
    target: SurvivalEventTarget = Query(
        default=SurvivalEventTarget.TASK_ABANDONMENT,
        description="Target outcome",
    ),
    task_id: Optional[uuid.UUID] = Query(default=None, description="Optional Task ID"),
    current_time_elapsed: float = Query(
        default=0.0, ge=0.0, description="Elapsed time t_curr since start"
    ),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DynamicSurvivalPredictionResponse:
    """
    Convenience GET endpoint to obtain dynamic survival predictions with zero future-leakage.
    """
    req = DynamicSurvivalPredictionRequest(
        target=target,
        user_id=user_id,
        task_id=task_id,
        current_time_elapsed=current_time_elapsed,
        update_trigger=DynamicUpdateTrigger.PERIODIC_TICK,
    )
    return DynamicSurvivalService.predict_survival(db=db, request=req)


@router.post(
    "/dynamic-update",
    response_model=DynamicSurvivalPredictionResponse,
    summary="Update survival curve in response to a real-time behavioral trigger",
)
def dynamic_survival_update(
    request: DynamicSurvivalPredictionRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DynamicSurvivalPredictionResponse:
    """
    Updates the ongoing survival curve conditioning on survival past t_curr and incorporating
    new real-time event triggers (e.g. NEW_INTERRUPTION, DEADLINE_APPROACHING).
    """
    if request.user_id is None:
        request.user_id = user_id
    return DynamicSurvivalService.dynamic_update(db=db, request=request)
