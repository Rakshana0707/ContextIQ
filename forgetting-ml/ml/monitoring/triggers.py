"""
triggers.py

Compound Retraining Triggers & Policy Engine (Phase 2.8).
Evaluates multi-factor conditions before recommending model retraining:
1. Persistent feature drift (requires multiple features; single alert filtered).
2. Prediction distribution changes (probability PSI or risk tier shift).
3. Concept drift / performance degradation (PR-AUC degradation on labeled window).
4. New labeled observations threshold (volume trigger).
5. Scheduled cadence intervals (time elapsed).

Guarantees:
A single statistical drift alert never proves model inaccuracy or forces retraining.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TriggerEvaluation:
    condition_name: str
    status: str  # "TRIGGERED", "WARNING", "OK"
    severity: str  # "HIGH", "MEDIUM", "LOW", "NONE"
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)


class RetrainingTriggerPolicy:
    """Evaluates multi-factor triggers to determine whether retraining is justified."""

    def __init__(
        self,
        min_drifted_features_for_trigger: int = 2,
        prediction_psi_trigger: float = 0.20,
        concept_pr_auc_drop_trigger: float = 0.10,
        min_new_labeled_samples: int = 1000,
        max_cadence_days: int = 30,
    ):
        self.min_drifted_features = min_drifted_features_for_trigger
        self.pred_psi_threshold = prediction_psi_trigger
        self.concept_drop_threshold = concept_pr_auc_drop_trigger
        self.min_samples = min_new_labeled_samples
        self.max_cadence_days = max_cadence_days

    def evaluate(
        self,
        feature_drift_result: Optional[Dict[str, Any]] = None,
        prediction_drift_result: Optional[Dict[str, Any]] = None,
        concept_drift_result: Optional[Dict[str, Any]] = None,
        new_labeled_count: int = 0,
        last_trained_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        evaluations: List[TriggerEvaluation] = []

        # 1. Feature Drift Evaluation
        if feature_drift_result:
            drifted = feature_drift_result.get("drifted_features_count", 0)
            moderate = feature_drift_result.get("moderate_features_count", 0)
            if drifted >= self.min_drifted_features:
                evaluations.append(TriggerEvaluation(
                    condition_name="feature_drift",
                    status="TRIGGERED",
                    severity="HIGH",
                    reason=f"{drifted} features exhibit significant distribution drift (PSI >= 0.20).",
                    metrics={"drifted_count": drifted, "moderate_count": moderate},
                ))
            elif drifted == 1 or moderate >= 3:
                evaluations.append(TriggerEvaluation(
                    condition_name="feature_drift",
                    status="WARNING",
                    severity="MEDIUM",
                    reason="Isolated feature shift detected. Single-feature alerts do not justify retraining.",
                    metrics={"drifted_count": drifted, "moderate_count": moderate},
                ))
            else:
                evaluations.append(TriggerEvaluation(
                    condition_name="feature_drift",
                    status="OK",
                    severity="NONE",
                    reason="Feature distributions match training baseline.",
                ))

        # 2. Prediction Drift Evaluation
        if prediction_drift_result:
            prob_psi = prediction_drift_result.get("probability_psi", 0.0)
            cat_js = prediction_drift_result.get("category_js_divergence", 0.0)
            if prob_psi >= self.pred_psi_threshold or cat_js >= 0.15:
                evaluations.append(TriggerEvaluation(
                    condition_name="prediction_drift",
                    status="TRIGGERED",
                    severity="HIGH",
                    reason=f"Significant prediction shift (Probability PSI={prob_psi:.3f}, Tier JSD={cat_js:.3f}).",
                    metrics={"probability_psi": prob_psi, "category_js": cat_js},
                ))
            elif prob_psi >= 0.10:
                evaluations.append(TriggerEvaluation(
                    condition_name="prediction_drift",
                    status="WARNING",
                    severity="LOW",
                    reason=f"Moderate prediction probability variance (PSI={prob_psi:.3f}).",
                    metrics={"probability_psi": prob_psi},
                ))
            else:
                evaluations.append(TriggerEvaluation(
                    condition_name="prediction_drift",
                    status="OK",
                    severity="NONE",
                    reason="Prediction distributions are consistent with baseline.",
                ))

        # 3. Concept Drift Evaluation (Ground-Truth Performance)
        if concept_drift_result:
            is_concept_drift = concept_drift_result.get("concept_drift_detected", False)
            drop = concept_drift_result.get("pr_auc_relative_drop", 0.0)
            if is_concept_drift:
                evaluations.append(TriggerEvaluation(
                    condition_name="concept_drift",
                    status="TRIGGERED",
                    severity="HIGH",
                    reason=f"Critical performance degradation: PR-AUC dropped {drop:.1%} on labeled window.",
                    metrics={"relative_pr_auc_drop": drop},
                ))
            elif concept_drift_result.get("status") == "INSUFFICIENT_LABELED_DATA":
                evaluations.append(TriggerEvaluation(
                    condition_name="concept_drift",
                    status="OK",
                    severity="NONE",
                    reason="Insufficient labeled tasks in current evaluation window.",
                ))
            else:
                evaluations.append(TriggerEvaluation(
                    condition_name="concept_drift",
                    status="OK",
                    severity="NONE",
                    reason="Model performance on verified tasks meets benchmark.",
                ))

        # 4. New Labeled Observations Volume Trigger
        if new_labeled_count >= self.min_samples:
            evaluations.append(TriggerEvaluation(
                condition_name="volume_threshold",
                status="TRIGGERED",
                severity="MEDIUM",
                reason=f"Accumulated {new_labeled_count} newly verified tasks (threshold: {self.min_samples}).",
                metrics={"new_samples": new_labeled_count},
            ))

        # 5. Scheduled Cadence Trigger
        if last_trained_timestamp:
            try:
                lt_dt = datetime.fromisoformat(last_trained_timestamp.replace("Z", "+00:00"))
                days_elapsed = (datetime.now(timezone.utc) - lt_dt).days
                if days_elapsed >= self.max_cadence_days:
                    evaluations.append(TriggerEvaluation(
                        condition_name="cadence_interval",
                        status="TRIGGERED",
                        severity="LOW",
                        reason=f"Scheduled maintenance interval reached ({days_elapsed} days since last train).",
                        metrics={"days_elapsed": days_elapsed},
                    ))
            except Exception:
                pass

        # Decision Synthesis
        triggered_conditions = [e for e in evaluations if e.status == "TRIGGERED"]
        has_concept_drift = any(e.condition_name == "concept_drift" and e.status == "TRIGGERED" for e in evaluations)
        has_dual_drift = (
            any(e.condition_name == "feature_drift" and e.status == "TRIGGERED" for e in evaluations) and
            any(e.condition_name == "prediction_drift" and e.status == "TRIGGERED" for e in evaluations)
        )
        has_volume = any(e.condition_name == "volume_threshold" and e.status == "TRIGGERED" for e in evaluations)
        has_cadence = any(e.condition_name == "cadence_interval" and e.status == "TRIGGERED" for e in evaluations)

        should_retrain = bool(has_concept_drift or has_dual_drift or has_volume or has_cadence)

        if has_concept_drift:
            rec_action = "RETRAIN_IMMEDIATE: Concept degradation confirmed by labeled ground truth."
            urgency = "HIGH"
        elif has_dual_drift:
            rec_action = "RETRAIN_RECOMMENDED: Compound feature and prediction drift observed."
            urgency = "HIGH"
        elif has_volume or has_cadence:
            rec_action = "RETRAIN_ROUTINE: Scheduled / volume threshold satisfied."
            urgency = "MEDIUM"
        elif any(e.status == "WARNING" for e in evaluations):
            rec_action = "MONITOR: Early warning signals observed; awaiting confirmation."
            urgency = "LOW"
        else:
            rec_action = "NO_ACTION_REQUIRED: Distributions stable."
            urgency = "NONE"

        return {
            "retraining_recommended": should_retrain,
            "recommended_action": rec_action,
            "urgency": urgency,
            "triggered_conditions_count": len(triggered_conditions),
            "conditions": [
                {
                    "name": e.condition_name,
                    "status": e.status,
                    "severity": e.severity,
                    "reason": e.reason,
                    "metrics": e.metrics,
                }
                for e in evaluations
            ],
        }
