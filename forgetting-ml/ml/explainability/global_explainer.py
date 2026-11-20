"""
global_explainer.py

Global explainability engine for ContextIQ (Phase 2.7).
Computes:
- Global feature importance rankings (mean |SHAP|)
- Feature dependence distributions
- Pairwise feature interaction profiles
- Serialization to artifacts/global_explanations.json and diagnostic plots
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap

from ml.explainability.feature_mapper import FeatureMapper


def _save(fig, path: Path, dpi: int = 150):
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


class GlobalExplainer:
    """Computes population-level SHAP importance, dependence curves, and interaction insights."""

    @classmethod
    def compute_global_summary(
        cls,
        shap_values: np.ndarray,
        feature_names: List[str],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Computes sorted global feature importance table:
        rank, feature, display_name, mean_abs_shap, percent_relative_importance
        """
        if shap_values.ndim == 3:
            # Multi-class or binary [samples, features, classes]
            shap_values = shap_values[:, :, 1]
        elif isinstance(shap_values, list):
            shap_values = shap_values[-1]

        mean_abs = np.mean(np.abs(shap_values), axis=0)
        total_importance = float(np.sum(mean_abs)) if np.sum(mean_abs) > 0 else 1.0

        order = np.argsort(mean_abs)[::-1][:top_k]
        rankings = []
        for rank, idx in enumerate(order, start=1):
            feat_name = feature_names[idx]
            raw_name, display_title, _ = FeatureMapper.parse_transformed_feature(feat_name)
            val = float(mean_abs[idx])
            rel_pct = (val / total_importance) * 100.0

            rankings.append({
                "rank": rank,
                "feature": feat_name,
                "raw_feature": raw_name,
                "display_name": display_title,
                "mean_abs_shap": round(val, 4),
                "relative_importance_pct": round(rel_pct, 2),
                "description": FeatureMapper.get_feature_description(raw_name),
            })
        return rankings

    @classmethod
    def compute_feature_interactions(
        cls,
        shap_values: np.ndarray,
        feature_names: List[str],
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Identifies top interacting feature pairs by SHAP value covariance/correlation.
        """
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]
        elif isinstance(shap_values, list):
            shap_values = shap_values[-1]

        n_features = shap_values.shape[1]
        cov_matrix = np.cov(shap_values, rowvar=False)

        pairs = []
        for i in range(n_features):
            for j in range(i + 1, n_features):
                strength = abs(cov_matrix[i, j])
                pairs.append((strength, i, j))

        pairs.sort(reverse=True, key=lambda x: x[0])
        top_pairs = []
        for strength, i, j in pairs[:top_n]:
            f1, f2 = feature_names[i], feature_names[j]
            _, d1, _ = FeatureMapper.parse_transformed_feature(f1)
            _, d2, _ = FeatureMapper.parse_transformed_feature(f2)
            top_pairs.append({
                "feature_a": f1,
                "feature_b": f2,
                "display_pair": f"{d1} × {d2}",
                "co_attribution_strength": round(float(strength), 4),
            })
        return top_pairs

    @classmethod
    def export_global_report_and_plots(
        cls,
        shap_values: np.ndarray,
        X_sample: np.ndarray,
        feature_names: List[str],
        model_name: str,
        model_version: str,
        artifacts_dir: Path,
    ) -> Dict[str, Any]:
        """
        Generates artifacts/global_explanations.json and saves diagnostic SHAP figures.
        """
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        summary = cls.compute_global_summary(shap_values, feature_names)
        interactions = cls.compute_feature_interactions(shap_values, feature_names)

        payload = {
            "model_name": model_name,
            "model_version": model_version,
            "explanation_version": "2.7.0",
            "global_importances": summary,
            "top_interactions": interactions,
        }

        # 1. Save JSON
        json_path = artifacts_dir / "global_explanations.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # 2. Save SHAP Summary Bar Plot
        fig, ax = plt.subplots(figsize=(8, 6))
        top_10 = summary[:10]
        y_pos = np.arange(len(top_10))[::-1]
        ax.barh(y_pos, [x["mean_abs_shap"] for x in top_10], color="#2563EB", align="center")
        ax.set_yticks(y_pos)
        ax.set_yticklabels([x["display_name"] for x in top_10])
        ax.set_xlabel("Mean |SHAP Value| (Impact on Model Log-Odds)")
        ax.set_title(f"Top 10 Global Behavioral Predictors ({model_name} v{model_version})")
        _save(fig, artifacts_dir / "shap_summary_bar.png")

        return payload
