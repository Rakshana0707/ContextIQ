"""
Causal Analysis & Confounding Evaluation REST API Endpoints (ContextIQ Phase 6.3).

Exposes:
- Causal research questions and DAG definitions.
- Target trial protocols avoiding immortal-time bias.
- Doubly robust and propensity score causal evaluations.
- Covariate balance (SMD), overlap diagnostics, and E-value sensitivity.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.causal_analysis import (
    CausalAnalysisResult,
    CausalDAGDefinition,
    CausalEvaluationRequest,
    CausalMethod,
    CausalQuestionId,
    TargetTrialProtocol,
)
from app.services.causal_service import CausalService

router = APIRouter(prefix="/causal", tags=["causal"])


@router.get(
    "/questions",
    response_model=List[Dict[str, Any]],
    summary="List all supported causal research questions",
)
def list_causal_questions() -> List[Dict[str, Any]]:
    """Returns summaries of all 4 supported causal research questions and their DAG specifications."""
    return CausalService.list_questions()


@router.get(
    "/dag/{question_id}",
    response_model=CausalDAGDefinition,
    summary="Retrieve Directed Acyclic Graph (DAG) for a causal question",
)
def get_causal_dag(question_id: CausalQuestionId) -> CausalDAGDefinition:
    """
    Returns full DAG definition with minimal sufficient adjustment sets,
    forbidden controls (colliders and mediators), and Mermaid diagram.
    """
    dag = CausalService.get_dag(question_id)
    if dag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Causal DAG not found for question: {question_id}",
        )
    return dag


@router.get(
    "/target-trials",
    response_model=List[TargetTrialProtocol],
    summary="List all Target Trial Protocols",
)
def list_target_trials() -> List[TargetTrialProtocol]:
    """Returns target trial specifications ensuring strict Time Zero (T0) alignment."""
    protocols = []
    for q in CausalQuestionId:
        p = CausalService.get_target_trial(q)
        if p is not None:
            protocols.append(p)
    return protocols


@router.get(
    "/target-trials/{question_id}",
    response_model=TargetTrialProtocol,
    summary="Retrieve Target Trial Protocol for a question",
)
def get_target_trial_protocol(question_id: CausalQuestionId) -> TargetTrialProtocol:
    """Returns target trial protocol specifying eligibility, strategies, T0, and outcome window."""
    protocol = CausalService.get_target_trial(question_id)
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target trial not found for question: {question_id}",
        )
    return protocol


@router.post(
    "/evaluate",
    response_model=CausalAnalysisResult,
    summary="Evaluate causal effect with confounding adjustment",
)
def evaluate_causal_question(
    request: CausalEvaluationRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CausalAnalysisResult:
    """
    Evaluates whether an intervention causally improves behavioral outcomes.
    Executes doubly robust estimation, assesses covariate balance, checks common support,
    and calculates E-values for unmeasured confounding.
    """
    if request.user_id is None:
        request.user_id = user_id
    return CausalService.evaluate_causal_question(db=db, request=request)


@router.get(
    "/evaluate/{question_id}",
    response_model=CausalAnalysisResult,
    summary="Evaluate causal effect for a question (GET convenience)",
)
def evaluate_causal_question_get(
    question_id: CausalQuestionId,
    method: CausalMethod = Query(default=CausalMethod.DOUBLY_ROBUST_AIPW),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> CausalAnalysisResult:
    """Convenience GET endpoint to evaluate a causal question using default or specified method."""
    req = CausalEvaluationRequest(question_id=question_id, method=method, user_id=user_id)
    return CausalService.evaluate_causal_question(db=db, request=req)
