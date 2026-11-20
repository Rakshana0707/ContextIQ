"""
train.py

ContextIQ Survival Analysis Training & Benchmarking Script
Phase 2.3 Specification Implementation

1. Generates / loads chronological survival dataset
2. Fits Kaplan-Meier, Cox Proportional Hazards, and Weibull AFT models
3. Evaluates on held-out test split (C-index, Brier scores, calibration)
4. Persists artifacts/survival_bundle.joblib
5. Generates markdown and JSON evaluation reports
"""

import sys
from pathlib import Path
import pandas as pd

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.survival.data import create_synthetic_survival_dataset
from ml.survival.models import SurvivalModelPipeline
from ml.survival.evaluation import evaluate_survival_pipeline, save_survival_reports

ARTIFACTS_DIR = ROOT / "artifacts"
DATASETS_DIR = ROOT / "datasets"


def main():
    print("=" * 60)
    print("ContextIQ Survival Analysis Subsystem Training")
    print("=" * 60)

    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    surv_path = DATASETS_DIR / "survival_tasks.csv"
    if not surv_path.exists():
        print("Generating synthetic survival dataset (N=5000, 60 days)...")
        df = create_synthetic_survival_dataset(n_samples=5000, seed=42)
        df.to_csv(surv_path, index=False)
    else:
        print(f"Loading existing survival dataset from {surv_path}...")
        df = pd.read_csv(surv_path)

    print(f"Dataset loaded: {len(df)} records.")
    event_rate = float(df["event_observed"].mean()) * 100
    print(f"Observed failure rate (E=1): {event_rate:.1f}% | Right-censored (E=0): {100-event_rate:.1f}%")

    # Chronological train/val/test split (70% train, 15% val, 15% test)
    n = len(df)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)

    train_df = df.iloc[:n_train].copy()
    val_df = df.iloc[n_train:n_train + n_val].copy()
    test_df = df.iloc[n_train + n_val:].copy()

    print(f"Split sizes -> Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # Fit survival models
    print("\nFitting Kaplan-Meier, Cox PH, and Weibull AFT models...")
    pipeline = SurvivalModelPipeline(penalizer=0.05)
    pipeline.fit(train_df)

    # Evaluate on held-out test split
    print("Evaluating models on held-out test split...")
    report = evaluate_survival_pipeline(pipeline, test_df)

    print("\nEvaluation Results:")
    print(f"  - Cox Concordance Index (C-Index): {report.c_index_cox:.4f}")
    print(f"  - Integrated Brier Score (IBS)  : {report.integrated_brier_score:.4f}")
    for h, bs in report.brier_scores_by_horizon.items():
        print(f"  - Brier Score at {h:4s}: {bs:.4f}")

    # Save bundle and reports
    bundle_path = ARTIFACTS_DIR / "survival_bundle.joblib"
    pipeline.save(bundle_path)
    print(f"\nSaved survival model bundle to: {bundle_path}")

    save_survival_reports(report, ARTIFACTS_DIR)
    print(f"Saved evaluation reports to: {ARTIFACTS_DIR}")
    print("Survival subsystem training complete!")


if __name__ == "__main__":
    main()
