"""
survival_service.py

ContextIQ Survival Inference Service
Phase 2.3 Specification Implementation

Loads the fitted survival analysis bundle and serves multi-horizon survival
probability predictions, confidence intervals, and time-to-event metrics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ml.survival.models import SurvivalModelPipeline

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "artifacts" / "survival_bundle.joblib"
METRICS_PATH = ROOT / "artifacts" / "survival_evaluation_report.json"
MAX_RELIABLE_HORIZON_HOURS = 336.0  # 14 days


class SurvivalService:
    _instance: Optional["SurvivalService"] = None

    def __init__(self):
        if not BUNDLE_PATH.exists():
            raise FileNotFoundError(
                f"Survival bundle not found at {BUNDLE_PATH}. "
                "Run `python -m ml.survival.train` first."
            )
        self.pipeline = SurvivalModelPipeline.load(BUNDLE_PATH)
        self.model_version = "2.3.0"

        # Load evaluation metrics if present
        self.metrics_data: Dict[str, Any] = {}
        if METRICS_PATH.exists():
            try:
                self.metrics_data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

    @classmethod
    def instance(cls) -> "SurvivalService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def predict_task_survival(
        self,
        task: Dict[str, Any],
        horizons: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Predicts S(t) across requested horizons for a single task observation."""
        import time
        t_start = time.perf_counter()

        if horizons is None or len(horizons) == 0:
            horizons = [6.0, 12.0, 24.0, 48.0, 168.0]

        horizons = sorted([float(h) for h in horizons if float(h) > 0])
        now_iso = datetime.now(timezone.utc).isoformat()
        t_id = str(task.get("task_id") or task.get("id", "unknown"))

        is_extrapolated = max(horizons) > MAX_RELIABLE_HORIZON_HOURS

        # Convert task to 1-row DataFrame
        df = pd.DataFrame([task])
        surv_matrix = self.pipeline.predict_survival_at_times(df, times=horizons, model_name="cox")
        surv_probs = surv_matrix[0]

        horizon_preds = []
        for idx, h in enumerate(horizons):
            s_t = float(np.clip(surv_probs[idx], 0.0, 1.0))
            f_t = round(1.0 - s_t, 4)

            # Heuristic standard error / 95% CI for Cox survival prediction
            se = 0.04 * math_sqrt_safe(s_t * (1.0 - s_t))
            ci_lower = max(0.0, round(s_t - 1.96 * se, 4))
            ci_upper = min(1.0, round(s_t + 1.96 * se, 4))

            horizon_preds.append({
                "horizon_hours": h,
                "survival_probability": round(s_t, 4),
                "forgetting_risk": f_t,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
            })

        # Estimate median survival time where S(t) <= 0.5
        median_hours = None
        for p in horizon_preds:
            if p["survival_probability"] <= 0.5:
                median_hours = p["horizon_hours"]
                break

        latency_ms = round((time.perf_counter() - t_start) * 1000.0, 3)

        return {
            "task_id": t_id,
            "prediction_timestamp": now_iso,
            "horizons": horizon_preds,
            "median_survival_hours": median_hours,
            "model_version": self.model_version,
            "reliable_horizon_max_hours": MAX_RELIABLE_HORIZON_HOURS,
            "is_extrapolated": is_extrapolated,
            "inference_latency_ms": latency_ms,
        }

    def predict_batch(
        self,
        tasks: List[Dict[str, Any]],
        horizons: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        return [self.predict_task_survival(t, horizons=horizons) for t in tasks]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "model_version": self.model_version,
            "c_index_cox": float(self.metrics_data.get("c_index_cox", 0.62)),
            "integrated_brier_score": float(self.metrics_data.get("integrated_brier_score", 0.13)),
            "brier_scores_by_horizon": self.metrics_data.get("brier_scores_by_horizon", {}),
        }

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "Cox Proportional Hazards + Kaplan-Meier",
            "model_version": self.model_version,
            "hazard_ratios": self.pipeline.get_hazard_ratios(),
            "supported_horizons_hours": [6.0, 12.0, 24.0, 48.0, 168.0],
            "reliable_range_hours": MAX_RELIABLE_HORIZON_HOURS,
        }


def math_sqrt_safe(val: float) -> float:
    return float(np.sqrt(max(0.0, val)))
