"""
inference.py

Loads the trained model bundle exactly once and exposes single / batch
prediction functions. No hardcoded predictions - every call routes through
the trained model artifact.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_LOCAL_DEPS = ROOT / "pydeps"
if _LOCAL_DEPS.exists():
    sys.path.insert(0, str(_LOCAL_DEPS))

from ml.explainability.explainer import ForgettingExplainer, risk_level_from_probability
from ml.training.config import MODEL_VERSION

ARTIFACT_PATH = ROOT / "artifacts" / "model_bundle.joblib"


class ForgettingPredictor:
    _instance = None

    def __init__(self):
        if not ARTIFACT_PATH.exists():
            raise FileNotFoundError(
                f"Model artifact not found at {ARTIFACT_PATH}. "
                "Run `python -m ml.training.train` first."
            )
        bundle = joblib.load(ARTIFACT_PATH)
        if not isinstance(bundle, dict):
            raise ValueError("Model artifact has an invalid format.")
        required_keys = {
            "model", "raw_model", "preprocessor", "model_name", "model_version",
            "threshold", "calibrated", "categorical_features", "numeric_features",
            "feature_names_transformed",
        }
        missing_keys = sorted(required_keys - bundle.keys())
        if missing_keys:
            raise ValueError(f"Model artifact is missing required fields: {missing_keys}")
        if bundle["model_version"] != MODEL_VERSION:
            raise ValueError(
                f"Model artifact version {bundle['model_version']!r} does not match "
                f"runtime version {MODEL_VERSION!r}."
            )
        if not isinstance(bundle["categorical_features"], list) or not isinstance(bundle["numeric_features"], list):
            raise ValueError("Model artifact feature metadata is invalid.")
        self.model = bundle["model"]
        self.raw_model = bundle["raw_model"]
        self.preprocessor = bundle["preprocessor"]
        self.model_name = bundle["model_name"]
        self.model_version = bundle["model_version"]
        self.threshold = bundle["threshold"]
        self.calibrated = bundle["calibrated"]
        self.categorical_features = bundle["categorical_features"]
        self.numeric_features = bundle["numeric_features"]
        self.feature_names_transformed = bundle["feature_names_transformed"]
        self.background_sample = bundle.get("background_sample")

        self.explainer = ForgettingExplainer(
            raw_model=self.raw_model,
            model_name=self.model_name,
            preprocessor=self.preprocessor,
            feature_names_transformed=self.feature_names_transformed,
            background_data=self.background_sample,
        )

        # Phase 2.5: Calibrator and Threshold Manager
        self.calibrator_bundle = None
        self.cal_pipeline = None
        self.risk_thresholds = None
        cal_path = ROOT / "artifacts" / "calibrator_bundle.joblib"
        if cal_path.exists():
            try:
                self.calibrator_bundle = joblib.load(cal_path)
                self.cal_pipeline = self.calibrator_bundle.get("pipeline")
                thresh_dict = self.calibrator_bundle.get("population_thresholds", {})
                from ml.calibration.thresholds import RiskThresholds
                self.risk_thresholds = RiskThresholds(
                    tau_low=thresh_dict.get("tau_low", 0.25),
                    tau_medium=thresh_dict.get("tau_medium", 0.45),
                    tau_high=thresh_dict.get("tau_high", 0.70),
                )
            except Exception:
                pass

        from ml.evaluation.cold_start import ColdStartStrategy
        self.cold_start_strategy = ColdStartStrategy()

    @classmethod
    def instance(cls) -> "ForgettingPredictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _to_dataframe(self, tasks: List[Dict[str, Any]]) -> pd.DataFrame:
        cols = self.categorical_features + self.numeric_features
        missing_by_task = {
            index: [column for column in cols if column not in task]
            for index, task in enumerate(tasks)
        }
        missing_by_task = {index: missing for index, missing in missing_by_task.items() if missing}
        if missing_by_task:
            raise ValueError(f"Missing required features by task: {missing_by_task}")
        df = pd.DataFrame(tasks)
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required features: {missing}")
        return df[cols]

    def predict_batch(self, tasks: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
        if not tasks:
            return []

        df = self._to_dataframe(tasks)
        X_transformed = self.preprocessor.transform(df)
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()

        probabilities = np.asarray(self.model.predict_proba(X_transformed))
        if probabilities.ndim != 2 or probabilities.shape[0] != len(tasks) or probabilities.shape[1] < 2:
            raise ValueError("Model returned an invalid probability matrix.")
        probabilities = probabilities[:, 1]
        if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
            raise ValueError("Model returned invalid prediction probabilities.")

        results = []
        for i, task in enumerate(tasks):
            row = X_transformed[i:i + 1]
            raw_prob = float(probabilities[i])
            if self.cal_pipeline is not None:
                cal_prob = float(self.cal_pipeline.calibrate(raw_prob))
            else:
                cal_prob = raw_prob

            # Legacy 3-tier level for strict backward compatibility
            risk_level_str = risk_level_from_probability(cal_prob)

            if self.risk_thresholds is not None:
                from ml.calibration.policy import get_risk_policy
                risk_cat = self.risk_thresholds.classify_risk(cal_prob)
                risk_category_str = risk_cat.value
                action_rec = get_risk_policy(risk_cat)["action_recommendation"]
                threshold = self.risk_thresholds.tau_medium
            else:
                risk_category_str = risk_level_str
                action_rec = None
                threshold = self.threshold

            reasons = self.explainer.explain(row, top_k=top_k)
            cs_assessment = self.cold_start_strategy.assess_user(
                previous_completions=task.get("previous_completion_count", 0),
                previous_forgettings=task.get("previous_forgetting_count", 0),
                raw_historical_rate=task.get("historical_forgetting_rate"),
            )
            ci_bounds = self.cold_start_strategy.calculate_prediction_interval(cal_prob, cs_assessment)

            results.append({
                "task": task.get("task_id"),
                "prediction_probability": round(cal_prob, 4),
                "raw_probability": round(raw_prob, 4),
                "calibrated_probability": round(cal_prob, 4),
                "risk_level": risk_level_str,
                "risk_category": risk_category_str,
                "classification_threshold": threshold,
                "calibration_version": "2.5.0",
                "model_version": self.model_version,
                "top_features": reasons,
                "action_recommendation": action_rec,
                "is_cold_start": cs_assessment.is_cold_start,
                "cold_start_tier": cs_assessment.cold_start_tier.value,
                "confidence_interval": [ci_bounds[0], ci_bounds[1]],
            })
        return results

    def predict_single(self, task: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
        return self.predict_batch([task], top_k=top_k)[0]

    def explain_single(self, task: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
        """Generates a detailed local explanation with attributions and grounded NLG."""
        df = self._to_dataframe([task])
        X_transformed = self.preprocessor.transform(df)
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()

        probabilities = np.asarray(self.model.predict_proba(X_transformed))[:, 1]
        raw_prob = float(probabilities[0])

        if self.cal_pipeline is not None:
            cal_prob = float(self.cal_pipeline.calibrate(raw_prob))
        else:
            cal_prob = raw_prob

        if self.risk_thresholds is not None:
            risk_cat = self.risk_thresholds.classify_risk(cal_prob).value
        else:
            risk_cat = risk_level_from_probability(cal_prob)

        return self.explainer.explain_local(
            raw_task=task,
            X_transformed_row=X_transformed[0:1],
            calibrated_prob=cal_prob,
            raw_prob=raw_prob,
            risk_category=risk_cat,
            top_k=top_k,
        )

    def explain_batch(self, tasks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Generates vectorized batch explanations."""
        if not tasks:
            return []

        df = self._to_dataframe(tasks)
        X_transformed = self.preprocessor.transform(df)
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()

        probabilities = np.asarray(self.model.predict_proba(X_transformed))[:, 1]

        results = []
        for i, task in enumerate(tasks):
            raw_p = float(probabilities[i])
            if self.cal_pipeline is not None:
                cal_p = float(self.cal_pipeline.calibrate(raw_p))
            else:
                cal_p = raw_p

            if self.risk_thresholds is not None:
                risk_cat = self.risk_thresholds.classify_risk(cal_p).value
            else:
                risk_cat = risk_level_from_probability(cal_p)

            res = self.explainer.explain_local(
                raw_task=task,
                X_transformed_row=X_transformed[i:i + 1],
                calibrated_prob=cal_p,
                raw_prob=raw_p,
                risk_category=risk_cat,
                top_k=top_k,
            )
            results.append(res)
        return results

    def get_global_explanation(self) -> Dict[str, Any]:
        """Fetches or dynamically computes global feature importances and interactions."""
        global_path = ROOT / "artifacts" / "global_explanations.json"
        if global_path.exists():
            try:
                with open(global_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Dynamically compute from background sample if artifact missing
        from ml.explainability.global_explainer import GlobalExplainer
        bg = self.background_sample
        if bg is None:
            return {
                "model_name": self.model_name,
                "model_version": self.model_version,
                "explanation_version": "2.7.0",
                "global_importances": [],
                "top_interactions": [],
            }

        if hasattr(bg, "toarray"):
            bg = bg.toarray()
        shap_vals = self.explainer._explainer.shap_values(bg) if self.explainer._explainer else None
        if shap_vals is not None:
            return GlobalExplainer.export_global_report_and_plots(
                shap_values=np.asarray(shap_vals),
                X_sample=bg,
                feature_names=self.feature_names_transformed,
                model_name=self.model_name,
                model_version=self.model_version,
                artifacts_dir=ROOT / "artifacts",
            )
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "explanation_version": "2.7.0",
            "global_importances": [],
            "top_interactions": [],
        }

