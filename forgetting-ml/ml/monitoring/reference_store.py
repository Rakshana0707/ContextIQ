"""
reference_store.py

Reference Baseline Profile and Production Observation Store (Phase 2.8).
Maintains:
1. Training baseline reference statistics (quantiles, deciles, category frequencies).
2. Model metadata and baseline performance benchmarks.
3. Sliding-window production observation buffer for live monitoring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ml.features.feature_spec import ALL_RAW_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
PROFILE_PATH = ARTIFACTS_DIR / "drift_reference_profile.json"
BUFFER_PATH = ARTIFACTS_DIR / "production_buffer.jsonl"


class ReferenceStore:
    """Manages training baseline reference profile and production observation buffer."""

    def __init__(
        self,
        profile_path: Path = PROFILE_PATH,
        buffer_path: Path = BUFFER_PATH,
    ):
        self.profile_path = profile_path
        self.buffer_path = buffer_path
        self._profile: Optional[Dict[str, Any]] = None

    def build_and_save_profile(
        self,
        train_df: pd.DataFrame,
        model_name: str,
        model_version: str,
        baseline_pr_auc: float = 0.4676,
        baseline_roc_auc: float = 0.6770,
        baseline_brier: float = 0.2234,
    ) -> Dict[str, Any]:
        """Builds statistical baseline profile from training data."""
        numeric_stats = {}
        for col in NUMERIC_FEATURES:
            if col in train_df.columns:
                vals = train_df[col].dropna().values
                quantiles = np.percentile(vals, np.linspace(0, 100, 11)).tolist()
                numeric_stats[col] = {
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)),
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals)),
                    "deciles": [float(q) for q in quantiles],
                    "sample_count": len(vals),
                }

        categorical_stats = {}
        for col in CATEGORICAL_FEATURES:
            if col in train_df.columns:
                counts = train_df[col].value_counts(normalize=True).to_dict()
                categorical_stats[col] = {str(k): float(v) for k, v in counts.items()}

        profile = {
            "model_name": model_name,
            "model_version": model_version,
            "feature_schema_version": "v1.1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "n_training_samples": len(train_df),
            "baseline_benchmarks": {
                "pr_auc": baseline_pr_auc,
                "roc_auc": baseline_roc_auc,
                "brier_score": baseline_brier,
            },
            "numeric_features": numeric_stats,
            "categorical_features": categorical_stats,
        }

        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        self._profile = profile
        return profile

    def load_profile(self) -> Dict[str, Any]:
        """Loads reference profile from disk."""
        if self._profile is not None:
            return self._profile

        if not self.profile_path.exists():
            return {}

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                self._profile = json.load(f)
                return self._profile
        except Exception:
            return {}

    def append_observation(
        self,
        task: Dict[str, Any],
        predicted_prob: float,
        risk_category: str,
        ground_truth: Optional[int] = None,
    ) -> None:
        """Appends a single prediction observation to the production buffer."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "predicted_prob": float(predicted_prob),
            "risk_category": risk_category,
            "ground_truth": ground_truth,
            **task,
        }
        self.buffer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.buffer_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_production_window(self, max_samples: int = 2000) -> pd.DataFrame:
        """Returns the most recent production observations as a DataFrame."""
        if not self.buffer_path.exists():
            return pd.DataFrame()

        rows = []
        try:
            with open(self.buffer_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        except Exception:
            return pd.DataFrame()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if len(df) > max_samples:
            df = df.iloc[-max_samples:].reset_index(drop=True)
        return df

    def clear_buffer(self) -> None:
        """Clears the production buffer."""
        if self.buffer_path.exists():
            self.buffer_path.unlink()
