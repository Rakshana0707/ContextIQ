"""
calibration_runner.py

ContextIQ Calibration & Threshold Optimization Runner (Phase 2.5).
Executes:
1. Model prediction on validation and test chronological splits.
2. Leakage-safe calibration fitting (strictly on val_df).
3. Diagnostic evaluation: Brier, Log Loss, ECE, Slope, and Intercept.
4. Utility-driven 4-tier threshold optimization.
5. Serialization of calibrator_bundle.joblib and generation of comprehensive reports.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.features.feature_spec import ALL_RAW_FEATURES
from ml.training.splits import chronological_split
from ml.calibration.calibrator import (
    ProbabilityCalibrationPipeline,
    compute_reliability_metrics,
)
from ml.calibration.thresholds import (
    RiskThresholds,
    derive_population_risk_thresholds,
    optimize_classification_threshold,
)
from ml.calibration.policy import POLICY_DESCRIPTIONS, RiskCategory

DATASET_PATH = ROOT / "datasets" / "tasks_raw.csv"
MODEL_BUNDLE_PATH = ROOT / "artifacts" / "model_bundle.joblib"
CALIBRATOR_BUNDLE_PATH = ROOT / "artifacts" / "calibrator_bundle.joblib"
ARTIFACTS_DIR = ROOT / "artifacts"
DOCS_DIR = ROOT / "docs"


def run_calibration_evaluation() -> Dict[str, Any]:
    print("=" * 70)
    print("ContextIQ Phase 2.5 — Advanced Probability Calibration & Thresholds")
    print("=" * 70)

    if not DATASET_PATH.exists() or not MODEL_BUNDLE_PATH.exists():
        raise FileNotFoundError("Prerequisite dataset or model bundle missing.")

    # 1. Load data and model bundle
    df = pd.read_csv(DATASET_PATH)
    train_df, val_df, test_df = chronological_split(df)
    print(f"Data splits: {len(train_df)} train, {len(val_df)} val, {len(test_df)} test.")

    bundle = joblib.load(MODEL_BUNDLE_PATH)
    preprocessor = bundle["preprocessor"]
    raw_model = bundle.get("raw_model", bundle["model"])

    feature_cols = [c for c in ALL_RAW_FEATURES if c in val_df.columns]
    target_col = "forgotten" if "forgotten" in val_df.columns else "will_forget"

    y_val = val_df[target_col].values
    y_test = test_df[target_col].values

    # 2. Extract raw model probabilities
    X_val_trans = preprocessor.transform(val_df[feature_cols])
    if hasattr(X_val_trans, "toarray"):
        X_val_trans = X_val_trans.toarray()

    X_test_trans = preprocessor.transform(test_df[feature_cols])
    if hasattr(X_test_trans, "toarray"):
        X_test_trans = X_test_trans.toarray()

    val_raw_probs = raw_model.predict_proba(X_val_trans)[:, 1]
    test_raw_probs = raw_model.predict_proba(X_test_trans)[:, 1]

    # 3. Fit calibration pipeline strictly on val_df
    print("\nFitting probability calibration pipeline on validation data...")
    cal_pipeline = ProbabilityCalibrationPipeline()
    cal_pipeline.fit(val_raw_probs, y_val)
    print(f"  -> Best calibration method selected: {cal_pipeline.best_method}")

    # 4. Evaluate each method on held-out test_df
    test_diagnostics: Dict[str, Dict[str, Any]] = {}
    
    # Baseline uncalibrated on test
    test_diagnostics["uncalibrated"] = compute_reliability_metrics(y_test, test_raw_probs)
    
    for name, cal in cal_pipeline.calibrators.items():
        if cal.is_fitted:
            cal_test_p = cal.predict_proba(test_raw_probs)
            test_diagnostics[name] = compute_reliability_metrics(y_test, cal_test_p)

    final_test_calibrated_probs = cal_pipeline.calibrate(test_raw_probs)
    final_val_calibrated_probs = cal_pipeline.calibrate(val_raw_probs)

    # 5. Derive Population Risk Thresholds on val_df
    print("\nDeriving intelligent risk thresholds on validation split...")
    thresholds = derive_population_risk_thresholds(y_val, final_val_calibrated_probs)
    print(f"  -> Thresholds: Low < {thresholds.tau_low} | Med: {thresholds.tau_low}-{thresholds.tau_medium} | High: {thresholds.tau_medium}-{thresholds.tau_high} | Critical >= {thresholds.tau_high}")

    # 6. Categorize test predictions
    test_categories = [thresholds.classify_risk(p) for p in final_test_calibrated_probs]
    category_counts = {cat.value: sum(1 for c in test_categories if c == cat) for cat in RiskCategory}
    print(f"  -> Test Risk Distribution: {category_counts}")

    # 7. Save Calibrator Bundle
    calibrator_bundle = {
        "pipeline": cal_pipeline,
        "best_method": cal_pipeline.best_method,
        "population_thresholds": thresholds.to_dict(),
        "validation_metrics": cal_pipeline.validation_metrics,
        "test_metrics": test_diagnostics,
        "calibration_version": "2.5.0",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    joblib.dump(calibrator_bundle, CALIBRATOR_BUNDLE_PATH, compress=3)
    print(f"Calibrator bundle saved to {CALIBRATOR_BUNDLE_PATH}")

    # 8. Save Metrics JSON
    metrics_json_path = ARTIFACTS_DIR / "calibration_metrics.json"
    metrics_payload = {
        "best_method": cal_pipeline.best_method,
        "thresholds": thresholds.to_dict(),
        "test_diagnostics": test_diagnostics,
        "validation_diagnostics": cal_pipeline.validation_metrics,
        "test_risk_distribution": category_counts,
    }
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    # 9. Generate Reliability Diagram Plot
    plot_reliability_diagrams(test_diagnostics, ARTIFACTS_DIR / "calibration_plot.png")

    # 10. Generate Markdown Reports
    generate_markdown_reports(cal_pipeline.best_method, thresholds, test_diagnostics, category_counts)

    print("\n" + "=" * 70)
    print("Phase 2.5 Calibration Runner Completed Successfully!")
    print("=" * 70)
    return metrics_payload


def plot_reliability_diagrams(test_diagnostics: Dict[str, Dict[str, Any]], out_path: Path) -> None:
    """Plots reliability curves comparing uncalibrated vs calibrated methods."""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect Calibration")

    colors = {"uncalibrated": "black", "platt": "#1f77b4", "isotonic": "#ff7f0e", "temperature": "#2ca02c"}
    
    for name, diag in test_diagnostics.items():
        if "bin_mean_predictions" in diag and "bin_fractions_positive" in diag:
            x = diag["bin_mean_predictions"]
            y = diag["bin_fractions_positive"]
            ax.plot(x, y, marker="o", label=f"{name.capitalize()} (ECE={diag['expected_calibration_error']:.3f})", color=colors.get(name, "blue"))

    ax.set_xlabel("Mean Predicted Probability")
    ax.set_ylabel("Empirical Fraction of Positives")
    ax.set_title("Reliability Diagram (Out-of-Time Test Set)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generate_markdown_reports(
    best_method: str,
    thresholds: RiskThresholds,
    test_diagnostics: Dict[str, Dict[str, Any]],
    risk_dist: Dict[str, int],
) -> None:
    lines = []
    lines.append("# ContextIQ — Probability Calibration & Risk Threshold Optimization Report")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append("Raw probabilistic outputs from machine learning models reflect relative ranking rather than true empirical frequencies. In Phase 2.5, we implemented an audited, multi-method calibration pipeline evaluating **Platt Scaling (Sigmoid)**, **Isotonic Regression**, and **Temperature Scaling** strictly on chronological validation data.")
    lines.append("")
    lines.append(f"- **Selected Calibration Method**: `{best_method}`")
    lines.append("- **Audit Rule**: Zero leakage. Calibration fit and threshold derivation were conducted exclusively on `val_df`. Unbiased evaluation conducted on held-out `test_df`.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Calibration Evaluation on Out-of-Time Test Set")
    lines.append("")
    lines.append("| Method | Brier Score | Log Loss | ECE | Slope ($\\beta_1$) | Intercept ($\\beta_0$) | Quality Interpretation |")
    lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---|")

    for name, m in test_diagnostics.items():
        brier = m.get("brier_score", 0.0)
        nll = m.get("log_loss", 0.0)
        ece = m.get("expected_calibration_error", 0.0)
        slope = m.get("calibration_slope", 1.0)
        intercept = m.get("calibration_intercept", 0.0)

        # Interpretation
        if ece <= 0.03:
            interp = "Excellent (Near-perfect match)"
        elif ece <= 0.08:
            interp = "Well-calibrated"
        else:
            interp = "Needs Refinement"

        lines.append(
            f"| `{name}` | {brier:.4f} | {nll:.4f} | **{ece:.4f}** | {slope:.3f} | {intercept:+.3f} | {interp} |"
        )

    lines.append("")
    lines.append("### Diagnostic Metric Interpretations:")
    lines.append("- **Brier Score**: Mean squared error of probabilities vs true outcomes. Lower is better ($0.0$ perfect, $0.25$ non-informative).")
    lines.append("- **Log Loss (Cross-Entropy)**: Heavily penalizes confident errors. Measures information-theoretic surprise.")
    lines.append("- **Expected Calibration Error (ECE)**: Weighted absolute discrepancy between predicted confidence and observed accuracy.")
    lines.append("- **Calibration Slope ($\\beta_1$)**: Ideal = 1.0. A slope $< 1.0$ indicates model overconfidence; $> 1.0$ indicates underconfidence.")
    lines.append("- **Calibration Intercept ($\\beta_0$)**: Ideal = 0.0. A positive intercept indicates systematic underestimation of risk.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Intelligent 4-Tier Risk Categorization")
    lines.append("")
    lines.append("We replaced arbitrary 0.33/0.66 cutoffs with utility-driven risk boundaries derived by balancing expected misclassification cost ($C_{FN} = 3 \\cdot C_{FP}$) and minimum precision constraints:")
    lines.append("")
    lines.append(f"- **LOW**: Probability $< {thresholds.tau_low:.2f}$")
    lines.append(f"- **MEDIUM**: ${thresholds.tau_low:.2f} \\le$ Probability $< {thresholds.tau_medium:.2f}$")
    lines.append(f"- **HIGH**: ${thresholds.tau_medium:.2f} \\le$ Probability $< {thresholds.tau_high:.2f}$")
    lines.append(f"- **CRITICAL**: Probability $\\ge {thresholds.tau_high:.2f}$")
    lines.append("")
    lines.append("### Test Set Risk Distribution:")
    lines.append(f"- `LOW`: **{risk_dist.get('LOW', 0)}** ({risk_dist.get('LOW', 0)/sum(risk_dist.values())*100:.1f}%)")
    lines.append(f"- `MEDIUM`: **{risk_dist.get('MEDIUM', 0)}** ({risk_dist.get('MEDIUM', 0)/sum(risk_dist.values())*100:.1f}%)")
    lines.append(f"- `HIGH`: **{risk_dist.get('HIGH', 0)}** ({risk_dist.get('HIGH', 0)/sum(risk_dist.values())*100:.1f}%)")
    lines.append(f"- `CRITICAL`: **{risk_dist.get('CRITICAL', 0)}** ({risk_dist.get('CRITICAL', 0)/sum(risk_dist.values())*100:.1f}%)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Personalized Threshold Strategy & Guardrails")
    lines.append("")
    lines.append("ContextIQ provides user-level adaptive threshold adjustments based on individual forgetting velocity:")
    lines.append("- **Strict Guardrail**: Requires a **minimum of 25 resolved tasks** in the user's historical profile.")
    lines.append("- **Cold-Start Fallback**: Users with $< 25$ tasks automatically fall back to population-level thresholds to prevent noisy overfitting.")
    lines.append("- **High-Forgetting Profile**: Lowers $\\tau_{\\text{medium}}$ and $\\tau_{\\text{high}}$ to increase early proactive nudging.")
    lines.append("- **Low-Forgetting Profile**: Raises thresholds slightly to preserve user attention and prevent alert fatigue.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Operational Risk Response Policy")
    lines.append("")
    lines.append("| Category | UI Treatment | Notification Channel | Operational Recommendation |")
    lines.append("|:---|:---|:---|:---|")
    for cat in RiskCategory:
        pol = POLICY_DESCRIPTIONS[cat]
        lines.append(f"| `{cat.value}` | Badge: {pol['ui_badge_color']} | `{pol['notification_channel'] or 'None'}` | {pol['action_recommendation']} |")
    lines.append("")

    report_content = "\n".join(lines)
    (ARTIFACTS_DIR / "calibration_report.md").write_text(report_content, encoding="utf-8")
    (DOCS_DIR / "PROBABILITY_CALIBRATION.md").write_text(report_content, encoding="utf-8")


if __name__ == "__main__":
    run_calibration_evaluation()
