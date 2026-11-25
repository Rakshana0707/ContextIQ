"""
Temporal Behavioral Sequence Prediction REST API Endpoints (ContextIQ Phase 6.5).

Exposes:
- Supported sequence prediction targets.
- Model registry and champion version metadata.
- Candidate architecture benchmarks (Tabular vs GRU vs TCN vs Transformer).
- Chronologically grounded sequence predictions.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.temporal_sequence import (
    BehavioralEventToken,
    ModelBenchmarkMetrics,
    SequencePredictionResponse,
    SequencePredictionTarget,
    SequenceRegistryMetadata,
)
from app.services.sequence_prediction_service import SequencePredictionService

router = APIRouter(prefix="/sequence", tags=["sequence-prediction"])


@router.get("/targets", summary="List supported sequence prediction targets")
def list_sequence_targets() -> List[Dict[str, str]]:
    """Returns list of supported sequence prediction targets with descriptions and horizons."""
    return SequencePredictionService.list_supported_targets()


@router.get("/registry", response_model=SequenceRegistryMetadata, summary="Retrieve sequence model registry")
def get_sequence_model_registry(
    target: SequencePredictionTarget = Query(
        default=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
        description="Target to inspect in registry",
    ),
) -> SequenceRegistryMetadata:
    """Returns model registry version, champion architecture, vocabulary, and candidate benchmarks."""
    return SequencePredictionService.get_model_registry(target=target)


@router.get(
    "/benchmark",
    response_model=List[ModelBenchmarkMetrics],
    summary="Benchmark sequence architectures against tabular baseline",
)
def get_sequence_benchmark(
    target: SequencePredictionTarget = Query(
        default=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
        description="Target to benchmark",
    ),
    force_rerun: bool = Query(default=False, description="Re-execute training and evaluation"),
) -> List[ModelBenchmarkMetrics]:
    """
    Evaluates candidate models (Tabular GradientBoosting, GRU, TCN, Causal Transformer)
    on strictly chronological splits and determines production champion.
    """
    return SequencePredictionService.get_or_run_benchmark(target=target, force_rerun=force_rerun)


@router.post(
    "/predict",
    response_model=SequencePredictionResponse,
    summary="Generate sequence prediction from event history",
)
def predict_sequence(
    target: SequencePredictionTarget = Query(
        default=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
        description="Prediction target",
    ),
    events: Optional[List[BehavioralEventToken]] = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SequencePredictionResponse:
    """
    Generates sequence prediction from historical event stream.
    Strictly forbids future-event leakage; handles cold start (length < 5) with widened uncertainty.
    """
    return SequencePredictionService.predict_sequence(
        db=db,
        user_id=user_id,
        target=target,
        provided_events=events,
    )


@router.get(
    "/predict",
    response_model=SequencePredictionResponse,
    summary="Generate sequence prediction from user history (GET convenience)",
)
def predict_sequence_get(
    target: SequencePredictionTarget = Query(
        default=SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION,
        description="Prediction target",
    ),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SequencePredictionResponse:
    """Convenience GET endpoint to forecast target from user's historical telemetry sequence."""
    return SequencePredictionService.predict_sequence(
        db=db,
        user_id=user_id,
        target=target,
    )
