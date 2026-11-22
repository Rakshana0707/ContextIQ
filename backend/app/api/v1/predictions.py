import uuid
import warnings
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.models.prediction import Prediction
from app.models.task import Task
from app.models.enums import PredictionType, TaskStatus
from app.schemas.prediction import (
    ForgettingPrediction,
    PredictionReason,
    RiskCategory,
    SurvivalEstimatePoint,
    TaskPredictionResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])

_ALLOWED_RISK_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


@router.get("/forgetting", response_model=List[ForgettingPrediction])
def list_predictions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    risk_level: Optional[str] = Query(default=None, max_length=16),
    risk_level_deprecated: Optional[str] = Query(
        default=None,
        alias="riskLevel",
        max_length=16,
        description="Deprecated alias for risk_level; will be removed in a future release.",
    ),
):
    effective_risk: Optional[str] = None
    if risk_level_deprecated is not None:
        warnings.warn(
            "The 'riskLevel' query parameter is deprecated; use 'risk_level' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        effective_risk = risk_level_deprecated
    if risk_level is not None:
        effective_risk = risk_level

    normalized_risk: Optional[str] = None
    if effective_risk is not None:
        normalized_risk = effective_risk.strip().upper()
        if normalized_risk not in _ALLOWED_RISK_LEVELS:
            raise ValidationError(f"Invalid risk_level: '{effective_risk}'. Allowed values: LOW, MEDIUM, HIGH, CRITICAL.")

    stmt = (
        select(Prediction)
        .where(Prediction.user_id == user_id)
        .where(Prediction.prediction_type == PredictionType.FORGET_RISK)
        .order_by(Prediction.created_at.desc())
    )
    predictions = list(db.scalars(stmt).all())

    if not predictions:
        tasks = list(db.scalars(
            select(Task)
            .where(Task.user_id == user_id, Task.status == TaskStatus.PENDING)
            .order_by(Task.created_at.desc())
            .limit(15)
        ).all())
        for t in tasks:
            PredictionService.predict_for_task(db=db, user_id=user_id, task_id=t.id)
        if tasks:
            predictions = list(db.scalars(stmt).all())

    result = []
    for p in predictions:
        val = p.predicted_value
        level = val.get("risk_level", "LOW")
        if normalized_risk and level != normalized_risk:
            continue

        survival_raw = val.get("survival_estimates")
        survival_pts = [SurvivalEstimatePoint(**pt) for pt in survival_raw] if survival_raw else None

        result.append(ForgettingPrediction(
            id=str(p.id),
            taskId=str(p.task_id) if p.task_id else "",
            taskTitle=val.get("taskTitle", "Unknown Task"),
            riskScore=round(p.confidence * 100, 1),
            riskLevel=level,
            reasons=[PredictionReason(**r) for r in val.get("reasons", [])],
            generatedAt=p.created_at.isoformat(),
            modelVersion=p.model_version,
            telemetryCoverage=val.get("telemetry_coverage"),
            survivalEstimates=survival_pts,
        ))
    return result


@router.get("/forgetting/task/{task_id}", response_model=ForgettingPrediction)
def get_task_prediction(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    stmt = (
        select(Prediction)
        .where(Prediction.user_id == user_id)
        .where(Prediction.task_id == task_id)
        .where(Prediction.prediction_type == PredictionType.FORGET_RISK)
        .order_by(Prediction.created_at.desc())
        .limit(1)
    )
    p = db.scalar(stmt)
    if not p:
        task = db.get(Task, task_id)
        if not task or task.user_id != user_id:
            raise NotFoundError("Prediction not found for task.")
        PredictionService.predict_for_task(db=db, user_id=user_id, task_id=task_id)
        p = db.scalar(stmt)
        if not p:
            raise NotFoundError("Prediction not found for task.")

    val = p.predicted_value
    survival_raw = val.get("survival_estimates")
    survival_pts = [SurvivalEstimatePoint(**pt) for pt in survival_raw] if survival_raw else None

    return ForgettingPrediction(
        id=str(p.id),
        taskId=str(p.task_id) if p.task_id else "",
        taskTitle=val.get("taskTitle", "Unknown Task"),
        riskScore=round(p.confidence * 100, 1),
        riskLevel=val.get("risk_level", "LOW"),
        reasons=[PredictionReason(**r) for r in val.get("reasons", [])],
        generatedAt=p.created_at.isoformat(),
        modelVersion=p.model_version,
        telemetryCoverage=val.get("telemetry_coverage"),
        survivalEstimates=survival_pts,
    )


@router.post("/tasks/{task_id}/predict", response_model=TaskPredictionResponse, status_code=status.HTTP_200_OK)
@router.post("/forgetting/task/{task_id}/predict", response_model=TaskPredictionResponse, status_code=status.HTTP_200_OK)
def trigger_task_prediction(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Generates an on-demand, live prediction and survival curve for a task using latest observed telemetry."""
    return PredictionService.predict_for_task(db=db, user_id=user_id, task_id=task_id)


@router.get("/tasks/{task_id}/survival", response_model=List[SurvivalEstimatePoint])
def get_task_survival_curve(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns multi-horizon survival probability estimates S(t) for a given task."""
    stmt = (
        select(Prediction)
        .where(Prediction.user_id == user_id)
        .where(Prediction.task_id == task_id)
        .where(Prediction.prediction_type == PredictionType.FORGET_RISK)
        .order_by(Prediction.created_at.desc())
        .limit(1)
    )
    p = db.scalar(stmt)
    if not p or not p.predicted_value.get("survival_estimates"):
        resp = PredictionService.predict_for_task(db=db, user_id=user_id, task_id=task_id)
        return resp.survival_estimates

    return [SurvivalEstimatePoint(**pt) for pt in p.predicted_value["survival_estimates"]]
