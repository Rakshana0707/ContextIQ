"""
Uncertainty-Aware Decision Support and Intelligent Abstention REST API Endpoints (ContextIQ Phase 6.8).

Exposes:
- Comprehensive model uncertainty audit across all 7 predictive model families.
- Calibration benchmarks (Platt, Isotonic, Temperature Scaling).
- Abstention outcome policies and fallback directives.
- Real-time decision support evaluation with aleatoric/epistemic decomposition.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.uncertainty_decision import (
    CalibrationMetrics,
    DecisionSupportRequest,
    DecisionSupportResponse,
    ModelUncertaintyAuditItem,
)
from app.services.uncertainty_decision_service import UncertaintyDecisionService

router = APIRouter(prefix="/uncertainty", tags=["uncertainty-decision-support"])


@router.get("/audit", response_model=List[ModelUncertaintyAuditItem], summary="Audit uncertainty across all models")
def audit_prediction_uncertainty() -> List[ModelUncertaintyAuditItem]:
    """
    Returns structured audit documenting uncertainty exposure, interval methodologies,
    calibration status, and known limitations across all 7 ContextIQ predictive model families.
    """
    return UncertaintyDecisionService.audit_all_models()


@router.get("/policies", summary="List typed abstention outcomes and policies")
def list_abstention_policies() -> List[Dict[str, Any]]:
    """Returns the 5 typed abstention outcomes, reasons, and downstream action policies."""
    return UncertaintyDecisionService.list_abstention_policies()


@router.get("/calibration", response_model=List[CalibrationMetrics], summary="Benchmark probability calibration methods")
def get_calibration_benchmarks() -> List[CalibrationMetrics]:
    """
    Evaluates Platt Scaling, Isotonic Regression, and Temperature Scaling
    on held-out validation data, reporting ECE, MCE, and Brier score.
    """
    return UncertaintyDecisionService.get_calibration_benchmarks()


@router.post(
    "/evaluate",
    response_model=DecisionSupportResponse,
    summary="Evaluate prediction uncertainty, coverage, and abstention policy",
)
def evaluate_decision_support(
    request: DecisionSupportRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DecisionSupportResponse:
    """
    Decomposes uncertainty into aleatoric and epistemic, audits data coverage,
    and returns explicit intelligent abstention outcome (PREDICTION_AVAILABLE, PREDICTION_WITH_CAUTION,
    INSUFFICIENT_EVIDENCE, UNSUPPORTED_INPUT, or MODEL_UNAVAILABLE).
    """
    if request.user_id is None:
        request.user_id = user_id
    return UncertaintyDecisionService.evaluate_decision_support(db=db, request=request)


@router.get(
    "/evaluate",
    response_model=DecisionSupportResponse,
    summary="Evaluate decision support for current user (GET convenience)",
)
def evaluate_decision_support_get(
    task_id: Optional[uuid.UUID] = Query(default=None, description="Active Task ID if applicable"),
    model_target: str = Query(default="forgetting_risk", description="Target model family"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DecisionSupportResponse:
    """
    Convenience GET endpoint to evaluate prediction reliability and abstention status.
    """
    req = DecisionSupportRequest(
        user_id=user_id,
        task_id=task_id,
        model_target=model_target,
    )
    return UncertaintyDecisionService.evaluate_decision_support(db=db, request=req)
