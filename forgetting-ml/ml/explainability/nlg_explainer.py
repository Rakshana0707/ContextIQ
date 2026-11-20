"""
nlg_explainer.py

Grounded Natural Language Explanation Generator (Phase 2.7).
Synthesizes fluent, intuitive behavioral reasoning strictly from verified
SHAP attributions and actual raw feature values.

Safety & Grounding Guarantees:
1. Zero hallucination: Every referenced quantity originates in the validated input.
2. Strictly non-causal: Phrased in associational / correlational terms.
3. Aligned with ContextIQ Intelligence Layer conventions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from ml.explainability.feature_mapper import FeatureMapper


class NLGExplainer:
    """Generates strictly grounded natural language explanations from SHAP attributions."""

    @classmethod
    def generate_explanation(
        cls,
        risk_category: str,
        probability: float,
        top_positive_factors: List[Dict[str, Any]],
        top_negative_factors: List[Dict[str, Any]],
        task_title: Optional[str] = None,
    ) -> str:
        """
        Constructs a concise, natural language explanation grounded in model outputs.
        """
        task_prefix = f"For '{task_title}', the" if task_title else "The"
        prob_pct = f"{probability * 100:.1f}%"

        # Risk level phrasing
        if risk_category in ("HIGH", "CRITICAL"):
            opening = f"{task_prefix} estimated forgetting risk is elevated at {prob_pct}."
        elif risk_category == "MEDIUM":
            opening = f"{task_prefix} task shows a moderate forgetting risk of {prob_pct}."
        else:
            opening = f"{task_prefix} task has a low forgetting risk of {prob_pct}."

        # Synthesize top increasing factors
        driver_phrases = []
        for factor in top_positive_factors[:2]:
            display = factor.get("display_name", factor.get("feature"))
            val_str = factor.get("actual_value_formatted", str(factor.get("actual_value", "")))
            if val_str and val_str != "N/A":
                driver_phrases.append(f"{display.lower()} ({val_str})")
            else:
                driver_phrases.append(display.lower())

        # Synthesize top protective factors
        protective_phrases = []
        for factor in top_negative_factors[:1]:
            display = factor.get("display_name", factor.get("feature"))
            val_str = factor.get("actual_value_formatted", str(factor.get("actual_value", "")))
            if val_str and val_str != "N/A":
                protective_phrases.append(f"{display.lower()} ({val_str})")
            else:
                protective_phrases.append(display.lower())

        sentences = [opening]

        if driver_phrases:
            drivers_joined = " and ".join(driver_phrases)
            sentences.append(
                f"This elevated vulnerability is primarily associated with {drivers_joined}."
            )

        if protective_phrases and risk_category in ("HIGH", "MEDIUM"):
            protective_joined = " and ".join(protective_phrases)
            sentences.append(
                f"Conversely, {protective_joined} acts as a moderating factor."
            )
        elif protective_phrases and risk_category == "LOW":
            protective_joined = " and ".join(protective_phrases)
            sentences.append(
                f"Strong retention is reinforced by {protective_joined}."
            )

        return " ".join(sentences)
