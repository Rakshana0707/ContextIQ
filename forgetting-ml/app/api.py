"""
api.py

Defines the FastAPI router for the Forgetting Prediction Engine.
"""

from fastapi import APIRouter, HTTPException

from app.schemas import (
    TaskFeatures, PredictionResponse, BatchPredictionRequest,
    BatchPredictionResponse, HealthResponse,
    SurvivalPredictionRequest, SurvivalPredictionResponse,
    BatchSurvivalRequest, BatchSurvivalResponse,
    SurvivalMetricsResponse, SurvivalModelInfoResponse,
    ExplanationResponse, BatchExplanationRequest, BatchExplanationResponse,
    GlobalExplanationResponse,
)
from app.inference import ForgettingPredictor
from app.survival_service import SurvivalService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    try:
        predictor = ForgettingPredictor.instance()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Model unavailable.") from exc
    return HealthResponse(
        status="ok",
        model_version=predictor.model_version,
        model_name=predictor.model_name,
    )


@router.post("/api/v1/predictions/forgetting", response_model=PredictionResponse, tags=["predictions"])
def predict_forgetting(task: TaskFeatures):
    try:
        predictor = ForgettingPredictor.instance()
        result = predictor.predict_single(task.model_dump())
        return PredictionResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail="Prediction service unavailable.") from e


@router.post("/api/v1/predictions/forgetting/batch", response_model=BatchPredictionResponse, tags=["predictions"])
def predict_forgetting_batch(request: BatchPredictionRequest):
    try:
        predictor = ForgettingPredictor.instance()
        tasks = [t.model_dump() for t in request.tasks]
        results = predictor.predict_batch(tasks)
        return BatchPredictionResponse(predictions=[PredictionResponse(**r) for r in results])
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail="Prediction service unavailable.") from e


# =====================================================================
# Survival Analysis Endpoints (Phase 2.3)
# =====================================================================

@router.post("/survival/predict", response_model=SurvivalPredictionResponse, tags=["survival"])
@router.post("/api/v1/survival/predict", response_model=SurvivalPredictionResponse, tags=["survival"])
def predict_survival(request: SurvivalPredictionRequest):
    try:
        service = SurvivalService.instance()
        result = service.predict_task_survival(
            task=request.task.model_dump(),
            horizons=request.horizons,
        )
        return SurvivalPredictionResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Survival prediction error: {str(e)}") from e


@router.post("/survival/batch_predict", response_model=BatchSurvivalResponse, tags=["survival"])
@router.post("/api/v1/survival/batch_predict", response_model=BatchSurvivalResponse, tags=["survival"])
def predict_survival_batch(request: BatchSurvivalRequest):
    try:
        service = SurvivalService.instance()
        tasks = [t.model_dump() for t in request.tasks]
        results = service.predict_batch(tasks=tasks, horizons=request.horizons)
        return BatchSurvivalResponse(predictions=[SurvivalPredictionResponse(**r) for r in results])
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Survival batch prediction error: {str(e)}") from e


@router.get("/survival/metrics", response_model=SurvivalMetricsResponse, tags=["survival"])
@router.get("/api/v1/survival/metrics", response_model=SurvivalMetricsResponse, tags=["survival"])
def get_survival_metrics():
    try:
        service = SurvivalService.instance()
        return SurvivalMetricsResponse(**service.get_metrics())
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch survival metrics: {str(e)}") from e


@router.get("/survival/model_info", response_model=SurvivalModelInfoResponse, tags=["survival"])
@router.get("/api/v1/survival/model_info", response_model=SurvivalModelInfoResponse, tags=["survival"])
def get_survival_model_info():
    try:
        service = SurvivalService.instance()
        return SurvivalModelInfoResponse(**service.get_model_info())
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch survival model info: {str(e)}") from e


# =====================================================================
# Explainability Endpoints (Phase 2.7)
# =====================================================================

@router.post("/explain", response_model=ExplanationResponse, tags=["explainability"])
@router.post("/api/v1/predictions/explain", response_model=ExplanationResponse, tags=["explainability"])
def explain_prediction(task: TaskFeatures, top_k: int = 5):
    try:
        predictor = ForgettingPredictor.instance()
        result = predictor.explain_single(task.model_dump(), top_k=top_k)
        return ExplanationResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation error: {str(e)}") from e


@router.post("/batch_explain", response_model=BatchExplanationResponse, tags=["explainability"])
@router.post("/api/v1/predictions/batch_explain", response_model=BatchExplanationResponse, tags=["explainability"])
def explain_prediction_batch(request: BatchExplanationRequest):
    try:
        predictor = ForgettingPredictor.instance()
        tasks = [t.model_dump() for t in request.tasks]
        results = predictor.explain_batch(tasks, top_k=request.top_k or 5)
        return BatchExplanationResponse(explanations=[ExplanationResponse(**r) for r in results])
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch explanation error: {str(e)}") from e


@router.get("/explain/global", response_model=GlobalExplanationResponse, tags=["explainability"])
@router.get("/api/v1/predictions/explain/global", response_model=GlobalExplanationResponse, tags=["explainability"])
def get_global_explanation():
    try:
        predictor = ForgettingPredictor.instance()
        return GlobalExplanationResponse(**predictor.get_global_explanation())
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Global explanation fetch error: {str(e)}") from e

