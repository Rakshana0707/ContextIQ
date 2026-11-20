"""
api.py

Defines the FastAPI router for the Forgetting Prediction Engine.
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parents[1]

from app.schemas import (
    TaskFeatures, PredictionResponse, BatchPredictionRequest,
    BatchPredictionResponse, HealthResponse,
    SurvivalPredictionRequest, SurvivalPredictionResponse,
    BatchSurvivalRequest, BatchSurvivalResponse,
    SurvivalMetricsResponse, SurvivalModelInfoResponse,
    ExplanationResponse, BatchExplanationRequest, BatchExplanationResponse,
    GlobalExplanationResponse,
    DriftReportResponse, RetrainingTriggerRequest, RetrainingStatusResponse,
    RetrainingApprovalRequest, RollbackRequest, RollbackResponse,
    DeploymentHistoryResponse,
)
from app.inference import ForgettingPredictor
from app.survival_service import SurvivalService
from ml.monitoring.drift_detector import DriftDetector
from ml.monitoring.reference_store import ReferenceStore
from ml.monitoring.retraining_pipeline import ControlledRetrainingPipeline
from ml.monitoring.rollback import ModelRollbackManager
from ml.monitoring.triggers import RetrainingTriggerPolicy

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


# =====================================================================
# Model Monitoring, Drift & Continual Learning Endpoints (Phase 2.8)
# =====================================================================

@router.get("/api/v1/monitoring/status", tags=["monitoring"])
def get_monitoring_status():
    try:
        predictor = ForgettingPredictor.instance()
        ref_store = ReferenceStore()
        pipeline = ControlledRetrainingPipeline()
        rollback_mgr = ModelRollbackManager()

        profile = ref_store.load_profile()
        retrain_status = pipeline.get_retraining_status()
        history = rollback_mgr.get_deployment_history()

        return {
            "status": "HEALTHY",
            "model_name": predictor.model_name,
            "model_version": predictor.model_version,
            "baseline_created_at": profile.get("created_at"),
            "baseline_benchmarks": profile.get("baseline_benchmarks", {}),
            "retraining_status": retrain_status.get("status", "IDLE"),
            "candidate_version_pending": retrain_status.get("candidate_version"),
            "total_deployments": len(history),
            "last_deployment": history[0] if history else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch monitoring status: {str(e)}") from e


@router.get("/api/v1/monitoring/drift/report", response_model=DriftReportResponse, tags=["monitoring"])
def get_drift_report():
    try:
        import numpy as np
        import pandas as pd
        from datetime import datetime, timezone
        from ml.features.feature_spec import CATEGORICAL_FEATURES, NUMERIC_FEATURES

        predictor = ForgettingPredictor.instance()
        ref_store = ReferenceStore()
        profile = ref_store.load_profile()

        # Load reference training data and production window
        train_path = ROOT / "datasets" / "tasks_raw.csv"
        if not train_path.exists():
            raise FileNotFoundError("Baseline dataset missing.")
        train_df = pd.read_csv(train_path)

        prod_df = ref_store.get_production_window(max_samples=1000)
        if prod_df.empty or len(prod_df) < 30:
            # When production buffer is small, evaluate most recent 10% slice of dataset as current window
            prod_df = train_df.iloc[-int(len(train_df) * 0.10):].copy()

        # 1. Feature Drift
        feat_drift = DriftDetector.evaluate_feature_drift(
            baseline_df=train_df,
            target_df=prod_df,
            numeric_features=NUMERIC_FEATURES,
            categorical_features=CATEGORICAL_FEATURES,
        )

        # 2. Prediction Drift
        base_probs = np.array([0.25] * len(train_df))  # Default reference distribution
        target_probs = np.array([0.27] * len(prod_df))
        if "predicted_prob" in prod_df.columns:
            target_probs = prod_df["predicted_prob"].dropna().values
        pred_drift = DriftDetector.evaluate_prediction_drift(
            baseline_probs=base_probs,
            target_probs=target_probs,
        )

        # 3. Concept Drift (if ground truth available)
        concept_drift = None
        if "forgotten" in prod_df.columns:
            y_true = prod_df["forgotten"].dropna().values
            base_pr_auc = profile.get("baseline_benchmarks", {}).get("pr_auc", 0.4676)
            # Evaluate using model pipeline
            cols = CATEGORICAL_FEATURES + NUMERIC_FEATURES
            X_trans = predictor.preprocessor.transform(prod_df[cols])
            if hasattr(X_trans, "toarray"):
                X_trans = X_trans.toarray()
            p_probs = predictor.model.predict_proba(X_trans)[:, 1]
            concept_drift = DriftDetector.evaluate_concept_drift(
                y_true=y_true,
                y_prob=p_probs,
                baseline_pr_auc=base_pr_auc,
            )

        # 4. Trigger Policy Decision
        policy = RetrainingTriggerPolicy()
        trigger_decision = policy.evaluate(
            feature_drift_result=feat_drift,
            prediction_drift_result=pred_drift,
            concept_drift_result=concept_drift,
            new_labeled_count=len(prod_df),
            last_trained_timestamp=profile.get("created_at"),
        )

        return DriftReportResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model_name=predictor.model_name,
            model_version=predictor.model_version,
            overall_status=feat_drift["status"],
            feature_drift_status=feat_drift["status"],
            drifted_features_count=feat_drift["drifted_features_count"],
            moderate_features_count=feat_drift["moderate_features_count"],
            total_features_evaluated=feat_drift["total_features_evaluated"],
            feature_details=feat_drift["feature_details"],
            prediction_drift=pred_drift,
            concept_drift=concept_drift,
            retraining_trigger_recommendation=trigger_decision,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate drift report: {str(e)}") from e


@router.post("/api/v1/monitoring/retrain/trigger", response_model=RetrainingStatusResponse, tags=["monitoring"])
def trigger_retraining(request: RetrainingTriggerRequest):
    try:
        pipeline = ControlledRetrainingPipeline()
        result = pipeline.run_candidate_pipeline(
            new_version=request.candidate_version or "1.2.0",
            candidate_model_type=request.candidate_model_type or "logistic_regression",
        )
        return RetrainingStatusResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining execution error: {str(e)}") from e


@router.get("/api/v1/monitoring/retrain/status", response_model=RetrainingStatusResponse, tags=["monitoring"])
def get_retraining_status():
    try:
        pipeline = ControlledRetrainingPipeline()
        return RetrainingStatusResponse(**pipeline.get_retraining_status())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get retraining status: {str(e)}") from e


@router.post("/api/v1/monitoring/retrain/approve", tags=["monitoring"])
def approve_candidate_deployment(request: RetrainingApprovalRequest):
    try:
        pipeline = ControlledRetrainingPipeline()
        res = pipeline.approve_and_deploy_challenger(
            approved_by=request.approved_by or "MLOps Admin",
            rationale=request.rationale or "Approved via API",
        )
        return res
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval error: {str(e)}") from e


@router.post("/api/v1/monitoring/retrain/reject", tags=["monitoring"])
def reject_candidate_deployment(reason: Optional[str] = "Rejected by MLOps operator"):
    try:
        pipeline = ControlledRetrainingPipeline()
        return pipeline.reject_challenger(reason=reason or "Rejected")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection error: {str(e)}") from e


@router.post("/api/v1/monitoring/rollback", response_model=RollbackResponse, tags=["monitoring"])
def rollback_model(request: RollbackRequest):
    try:
        rollback_mgr = ModelRollbackManager()
        res = rollback_mgr.rollback(
            target_version=request.target_version,
            approved_by=request.approved_by or "MLOps Admin",
            reason=request.reason or "Rollback requested",
        )
        return RollbackResponse(**res)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback error: {str(e)}") from e


@router.get("/api/v1/monitoring/history", response_model=DeploymentHistoryResponse, tags=["monitoring"])
def get_deployment_history():
    try:
        rollback_mgr = ModelRollbackManager()
        history = rollback_mgr.get_deployment_history()
        return DeploymentHistoryResponse(
            total_events=len(history),
            history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch deployment history: {str(e)}") from e


