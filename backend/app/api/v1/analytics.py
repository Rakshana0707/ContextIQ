import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.behaviour_metric import BehaviourMetric
from app.models.recommendation import Recommendation
from app.schemas.analytics import BehaviourMetricRead, RecommendationRead
from app.schemas.recovery_analytics import (
    BehavioralFrictionResponse,
    InterruptionTrendsResponse,
    PersonalBaselineResponse,
    RecoveryMetricsResponse,
)
from app.services.recovery_analytics import RecoveryAnalyticsService

router = APIRouter(tags=["analytics"])


# ---------------------------------------------------------------------------
# Automated Recovery & Micro-Delay Analytics (Phase 3.7)
# ---------------------------------------------------------------------------

@router.get("/analytics/recovery", response_model=RecoveryMetricsResponse)
@router.get("/recovery", response_model=RecoveryMetricsResponse)
def get_recovery_analytics(
    period_days: int = Query(30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Calculates three-tier resumption lag, recovery time variability, and focus spans."""
    return RecoveryAnalyticsService.get_recovery_metrics(
        db=db, user_id=user_id, period_days=period_days
    )


@router.get("/analytics/friction", response_model=BehavioralFrictionResponse)
@router.get("/friction", response_model=BehavioralFrictionResponse)
def get_behavioral_friction_index(
    period_days: int = Query(30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns calibrated Behavioral Friction Index (0-100) preventing double counting."""
    return RecoveryAnalyticsService.get_behavioral_friction_index(
        db=db, user_id=user_id, period_days=period_days
    )


@router.get("/analytics/interruption-trends", response_model=InterruptionTrendsResponse)
@router.get("/interruption-trends", response_model=InterruptionTrendsResponse)
def get_interruption_trends(
    period_days: int = Query(30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Breaks down interruption frequency and recovery across circadian, app, and type contexts."""
    return RecoveryAnalyticsService.get_interruption_trends(
        db=db, user_id=user_id, period_days=period_days
    )


@router.get("/analytics/personal-baseline", response_model=PersonalBaselineResponse)
@router.get("/personal-baseline", response_model=PersonalBaselineResponse)
def get_personal_baseline(
    baseline_days: int = Query(14, ge=3, le=90),
    current_days: int = Query(3, ge=1, le=30),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Evaluates self-relative personal baseline and recent behavioral deviation trends."""
    return RecoveryAnalyticsService.get_personal_baseline(
        db=db, user_id=user_id, baseline_period_days=baseline_days, current_period_days=current_days
    )


# ---------------------------------------------------------------------------
# Existing Analytics Feeds (Preserved)
# ---------------------------------------------------------------------------

@router.get("/behaviour-metrics", response_model=list[BehaviourMetricRead])
def list_behaviour_metrics(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Read-only feed for dashboard charts. Rows are written by the ML/analytics pipeline."""
    stmt = (
        select(BehaviourMetric)
        .where(BehaviourMetric.user_id == user_id)
        .order_by(BehaviourMetric.metric_date.asc())
    )
    return list(db.scalars(stmt).all())



@router.get("/context-switch-timeline")
async def get_context_switch_timeline(
    user_id: uuid.UUID = Depends(get_current_user_id),
    period_days: int = Query(30, ge=1, le=3650),
):
    settings = get_settings()
    url = f"{settings.DATA_ENGINE_URL.rstrip('/')}/analytics/context-switch-timeline"
    params = {"user_id": str(user_id), "period_days": period_days}
    try:
        async with httpx.AsyncClient(timeout=settings.ORCHESTRATOR_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to contact data engine: {e}")


@router.get("/task-context-heatmap")
async def get_task_context_heatmap(
    user_id: uuid.UUID = Depends(get_current_user_id),
    period_days: int = Query(30, ge=1, le=3650),
    value_metric: str = Query("completion_rate", pattern="^(completion_rate|forget_rate)$"),
):
    settings = get_settings()
    url = f"{settings.DATA_ENGINE_URL.rstrip('/')}/analytics/task-context-heatmap"
    params = {
        "user_id": str(user_id),
        "period_days": period_days,
        "value_metric": value_metric,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ORCHESTRATOR_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to contact data engine: {e}")


@router.get("/analytics/feedback/candidate-dataset")
@router.get("/feedback/candidate-dataset")
def export_candidate_dataset(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Exports user-validated interruption ground truth and task outcomes
    as candidate training records for offline calibration.
    """
    from app.services.feedback_loop_service import FeedbackLoopService
    return FeedbackLoopService.export_candidate_training_dataset(db=db, user_id=user_id)


# ---------------------------------------------------------------------------
# Phase 6.2 Cognitive Recovery Duration Prediction
# ---------------------------------------------------------------------------

@router.get("/analytics/recovery/prediction")
@router.get("/recovery/prediction")
def get_recovery_prediction(
    user_id: uuid.UUID = Depends(get_current_user_id),
    task_id: Optional[uuid.UUID] = Query(default=None),
    interruption_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Predicts cognitive recovery duration and resumption probability for current context."""
    from app.schemas.recovery_prediction import RecoveryPredictionRequest
    from app.services.recovery_prediction_service import RecoveryPredictionService
    req = RecoveryPredictionRequest(user_id=user_id, task_id=task_id, interruption_id=interruption_id)
    return RecoveryPredictionService.predict_recovery_duration(db=db, user_id=user_id, request=req)


@router.post("/analytics/recovery/prediction")
@router.post("/recovery/prediction")
def predict_recovery_duration_custom(
    payload: Optional[dict] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Predicts cognitive recovery duration for custom context parameters."""
    from app.schemas.recovery_prediction import RecoveryPredictionRequest
    from app.services.recovery_prediction_service import RecoveryPredictionService
    req = RecoveryPredictionRequest(**(payload or {}))
    return RecoveryPredictionService.predict_recovery_duration(db=db, user_id=user_id, request=req)


@router.get("/analytics/recovery/benchmark")
@router.get("/recovery/benchmark")
def get_recovery_benchmark_metrics(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Returns benchmark comparison across the 5 survival/duration modeling approaches."""
    from app.services.recovery_prediction_service import RecoveryPredictionService
    return RecoveryPredictionService.get_benchmark_comparison()


@router.get("/analytics/causal/questions")
def get_causal_questions(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Returns supported causal research questions, adjustment sets, and DAGs."""
    from app.services.causal_service import CausalService
    return CausalService.list_questions()


@router.get("/analytics/causal/evaluate")
def evaluate_causal_question_analytics(
    question_id: str = "recovery_buffer_on_resumption",
    method: str = "doubly_robust_aipw",
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Evaluates causal effect for a specified question via analytics router."""
    from app.schemas.causal_analysis import CausalEvaluationRequest, CausalMethod, CausalQuestionId
    from app.services.causal_service import CausalService

    req = CausalEvaluationRequest(
        question_id=CausalQuestionId(question_id),
        method=CausalMethod(method),
        user_id=user_id,
    )
    return CausalService.evaluate_causal_question(db=db, request=req)


@router.get("/analytics/counterfactual/compare")
def compare_counterfactuals_analytics(
    learner: str = "doubly_robust_learner",
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Compares counterfactual intervention candidates via analytics router."""
    from app.schemas.counterfactual import CounterfactualComparisonRequest, CounterfactualLearnerType
    from app.services.counterfactual_service import CounterfactualService

    req = CounterfactualComparisonRequest(
        user_id=user_id,
        learner=CounterfactualLearnerType(learner),
    )
    return CounterfactualService.compare_interventions(db=db, request=req)


@router.get("/analytics/sequence/predict")
def predict_sequence_analytics(
    target: str = "short_term_task_resumption",
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Forecasts target using sequence model via analytics router."""
    from app.schemas.temporal_sequence import SequencePredictionTarget
    from app.services.sequence_prediction_service import SequencePredictionService

    return SequencePredictionService.predict_sequence(
        db=db,
        user_id=user_id,
        target=SequencePredictionTarget(target),
    )


@router.get("/analytics/sequence/benchmark")
def get_sequence_benchmark_analytics(
    target: str = "short_term_task_resumption",
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieves candidate sequence model benchmark via analytics router."""
    from app.schemas.temporal_sequence import SequencePredictionTarget
    from app.services.sequence_prediction_service import SequencePredictionService

    return SequencePredictionService.get_or_run_benchmark(target=SequencePredictionTarget(target))


@router.get("/analytics/survival/predict")
def predict_survival_analytics(
    target: str = "task_abandonment",
    current_time_elapsed: float = 0.0,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Forecasts conditional survival curve via analytics router."""
    from app.schemas.dynamic_survival import DynamicSurvivalPredictionRequest, SurvivalEventTarget
    from app.services.dynamic_survival_service import DynamicSurvivalService

    req = DynamicSurvivalPredictionRequest(
        target=SurvivalEventTarget(target),
        user_id=user_id,
        current_time_elapsed=current_time_elapsed,
    )
    return DynamicSurvivalService.predict_survival(db=db, request=req)


@router.get("/analytics/survival/benchmark")
def get_survival_benchmark_analytics(
    target: str = "task_abandonment",
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieves candidate survival model benchmark via analytics router."""
    from app.schemas.dynamic_survival import SurvivalEventTarget
    from app.services.dynamic_survival_service import DynamicSurvivalService

    return DynamicSurvivalService.get_or_run_benchmark(target=SurvivalEventTarget(target))





