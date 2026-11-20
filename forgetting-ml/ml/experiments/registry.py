"""
registry.py

Structured Experiment Registry for Tabular Model Benchmarking.
Maintains persistent JSON and CSV records of all trained model candidates,
hyperparameters, evaluation metrics, and operational performance.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
REGISTRY_JSON_PATH = ARTIFACTS_DIR / "experiment_registry.json"
REGISTRY_CSV_PATH = ARTIFACTS_DIR / "experiment_registry.csv"


def compute_expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Computes Expected Calibration Error (ECE) across uniform probability bins."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    ece = 0.0
    n = len(y_true)

    for i in range(n_bins):
        mask = bin_indices == i
        if np.any(mask):
            bin_conf = np.mean(y_prob[mask])
            bin_acc = np.mean(y_true[mask])
            bin_weight = np.sum(mask) / n
            ece += bin_weight * abs(bin_acc - bin_conf)

    return float(round(ece, 4))


class ExperimentRegistry:
    """Manages the experiment tracking registry."""

    def __init__(self, json_path: Path = REGISTRY_JSON_PATH):
        self.json_path = json_path
        self.csv_path = json_path.with_suffix(".csv")
        self.records: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self.json_path.exists():
            try:
                return json.loads(self.json_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def log_experiment(
        self,
        experiment_id: str,
        model_type: str,
        hyperparameters: Dict[str, Any],
        metrics: Dict[str, Any],
        operational: Dict[str, Any],
        dataset_version: str = "1.0.0",
        feature_version: str = "v1.1",
        random_seed: int = 42,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Logs an experiment run into the registry."""
        entry = {
            "experiment_id": experiment_id,
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "model_type": model_type,
            "dataset_version": dataset_version,
            "feature_version": feature_version,
            "random_seed": random_seed,
            "hyperparameters": hyperparameters,
            "metrics": metrics,
            "operational": operational,
            "notes": notes,
        }
        # Update or append
        existing_idx = next((i for i, r in enumerate(self.records) if r["experiment_id"] == experiment_id), None)
        if existing_idx is not None:
            self.records[existing_idx] = entry
        else:
            self.records.append(entry)

        self.save()
        return entry

    def save(self) -> None:
        """Persists registry to disk as both JSON and flat CSV summary."""
        self.json_path.parent.mkdir(exist_ok=True, parents=True)
        self.json_path.write_text(json.dumps(self.records, indent=2), encoding="utf-8")

        # Flat CSV representation
        flat_rows = []
        for r in self.records:
            row = {
                "experiment_id": r["experiment_id"],
                "timestamp": r["training_timestamp"],
                "model_type": r["model_type"],
                "feature_version": r["feature_version"],
                "seed": r["random_seed"],
            }
            # Flatten metrics
            for k, v in r.get("metrics", {}).items():
                if isinstance(v, (int, float, str, bool)):
                    row[f"m_{k}"] = v
            # Flatten operational
            for k, v in r.get("operational", {}).items():
                if isinstance(v, (int, float, str, bool)):
                    row[f"op_{k}"] = v
            flat_rows.append(row)

        if flat_rows:
            df = pd.DataFrame(flat_rows)
            df.to_csv(self.csv_path, index=False)

    def get_summary_dataframe(self) -> pd.DataFrame:
        """Returns a formatted comparison table of all registered experiments."""
        if not self.records:
            return pd.DataFrame()
        flat_rows = []
        for r in self.records:
            m = r.get("metrics", {})
            op = r.get("operational", {})
            flat_rows.append({
                "Experiment ID": r["experiment_id"],
                "Model Type": r["model_type"],
                "PR-AUC": m.get("pr_auc", 0.0),
                "ROC-AUC": m.get("roc_auc", 0.0),
                "F1": m.get("f1", 0.0),
                "Precision": m.get("precision", 0.0),
                "Recall": m.get("recall", 0.0),
                "Brier": m.get("brier_score", 0.0),
                "ECE": m.get("ece", 0.0),
                "Train Time (s)": op.get("training_duration_s", 0.0),
                "Single Latency (ms)": op.get("single_latency_ms", 0.0),
                "Size (KB)": op.get("model_size_kb", 0.0),
            })
        df = pd.DataFrame(flat_rows)
        return df.sort_values(by="PR-AUC", ascending=False).reset_index(drop=True)
