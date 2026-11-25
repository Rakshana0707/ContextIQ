"""
Dual-Loop Reward Attribution Pipeline adapter (Phase 4.6).
Synthesizes immediate explicit user responses (Loop 1) and downstream
behavioral improvements (Loop 2) into a bounded ground-truth reward R_t in [-1.0, 1.0].
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class DualLoopRewardAttributor:
    """Computes verifiable composite rewards from explicit feedback and telemetry deltas."""

    EXPLICIT_WEIGHT = 0.40
    BEHAVIORAL_WEIGHT = 0.60

    @classmethod
    def compute_explicit_reward(
        cls,
        action: str,
        response_latency_seconds: Optional[float] = None,
    ) -> float:
        """
        Computes Loop 1 explicit reward R_explicit in [-1.0, 1.0].
        """
        act = action.upper().strip()
        if act == "ACCEPTED":
            base = 1.0
            if response_latency_seconds is not None and 0.0 < response_latency_seconds < 5.0:
                base = min(1.0, base + 0.1)
            return base
        elif act in {"SNOOZED", "DEFERRED"}:
            return 0.2
        elif act == "EXPIRED":
            return -0.2
        elif act == "DISMISSED":
            return -0.5
        elif act in {"EXPLICIT_NEGATIVE", "REPORTED_IRRELEVANT"}:
            return -1.0
        elif act in {"NOOP_OBSERVED", "NONE"}:
            return 0.0
        else:
            return 0.0

    @classmethod
    def compute_behavioral_reward(
        cls,
        resumption_lag_seconds: Optional[float] = None,
        baseline_lag_seconds: float = 45.0,
        friction_index_after: Optional[float] = None,
        friction_index_before: float = 50.0,
        task_completed: Optional[bool] = None,
        subsequent_interruptions_count: Optional[int] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Computes Loop 2 downstream behavioral reward R_behavioral in [-1.0, 1.0].
        """
        evidence: Dict[str, Any] = {}

        delta_lag_norm = 0.0
        if resumption_lag_seconds is not None:
            raw_delta_lag = baseline_lag_seconds - resumption_lag_seconds
            delta_lag_norm = max(-1.0, min(1.0, raw_delta_lag / max(30.0, baseline_lag_seconds)))
            evidence["delta_resumption_lag_norm"] = round(delta_lag_norm, 3)

        delta_bfi_norm = 0.0
        if friction_index_after is not None:
            raw_delta_bfi = friction_index_before - friction_index_after
            delta_bfi_norm = max(-1.0, min(1.0, raw_delta_bfi / 100.0))
            evidence["delta_bfi_norm"] = round(delta_bfi_norm, 3)

        comp_val = 0.0
        if task_completed is not None:
            comp_val = 1.0 if task_completed else 0.0
            evidence["task_completed_in_window"] = bool(task_completed)

        churn_pen = 0.0
        if subsequent_interruptions_count is not None:
            churn_pen = max(0.0, min(1.0, subsequent_interruptions_count / 5.0))
            evidence["disruption_churn_penalty"] = round(churn_pen, 3)

        r_beh = (
            0.35 * delta_lag_norm
            + 0.30 * delta_bfi_norm
            + 0.25 * comp_val
            - 0.10 * churn_pen
        )
        r_beh = max(-1.0, min(1.0, r_beh))
        evidence["r_behavioral_score"] = round(r_beh, 3)
        return r_beh, evidence

    @classmethod
    def synthesize_composite_reward(
        cls,
        action: str,
        response_latency_seconds: Optional[float] = None,
        resumption_lag_seconds: Optional[float] = None,
        baseline_lag_seconds: float = 45.0,
        friction_index_after: Optional[float] = None,
        friction_index_before: float = 50.0,
        task_completed: Optional[bool] = None,
        subsequent_interruptions_count: Optional[int] = None,
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        """
        Synthesizes composite reward R_t in [-1.0, 1.0] and full attribution evidence.
        """
        r_exp = cls.compute_explicit_reward(
            action=action,
            response_latency_seconds=response_latency_seconds,
        )

        has_behavioral_data = (
            resumption_lag_seconds is not None
            or friction_index_after is not None
            or task_completed is not None
            or subsequent_interruptions_count is not None
        )

        if has_behavioral_data:
            r_beh, beh_evidence = cls.compute_behavioral_reward(
                resumption_lag_seconds=resumption_lag_seconds,
                baseline_lag_seconds=baseline_lag_seconds,
                friction_index_after=friction_index_after,
                friction_index_before=friction_index_before,
                task_completed=task_completed,
                subsequent_interruptions_count=subsequent_interruptions_count,
            )
            composite = cls.EXPLICIT_WEIGHT * r_exp + cls.BEHAVIORAL_WEIGHT * r_beh
            evidence = {
                "action": action,
                "r_explicit": round(r_exp, 3),
                **beh_evidence,
                "composite_formula": "0.40 * R_explicit + 0.60 * R_behavioral",
                "composite_reward": round(composite, 3),
            }
        else:
            r_beh = 0.0
            composite = r_exp
            evidence = {
                "action": action,
                "r_explicit": round(r_exp, 3),
                "r_behavioral": 0.0,
                "composite_formula": "R_explicit_only",
                "composite_reward": round(composite, 3),
            }

        composite = max(-1.0, min(1.0, round(composite, 4)))
        return composite, r_exp, r_beh, evidence
