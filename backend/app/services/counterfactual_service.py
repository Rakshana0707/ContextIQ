"""
Counterfactual Recommendation and Intervention Service (ContextIQ Phase 6.4).

Provides:
- Point-in-time counterfactual comparisons across candidate interventions.
- Integration with Recommendation Engine: overrides heuristics when counterfactual evidence
  is validated and uncertainty is within tolerance, falling back to deterministic rules otherwise.
- Transparent reporting of potential outcomes, incremental benefits, uncertainty intervals,
  and exclusion reasons for unsupported options.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.counterfactual import (
    CandidateIntervention,
    CounterfactualCandidateResult,
    CounterfactualComparisonRequest,
    CounterfactualComparisonResponse,
    CounterfactualLearnerType,
    DataCoverageTier,
    RecommendationStrategy,
)
from app.services.counterfactual_dataset import CounterfactualDatasetBuilder
from app.services.counterfactual_learners import CounterfactualLearnerPipeline

logger = logging.getLogger(__name__)


class CounterfactualService:
    """
    Coordinates counterfactual intervention forecasting, candidate comparisons,
    and recommendation optimization with safety fallbacks.
    """

    _cached_pipeline: Optional[CounterfactualLearnerPipeline] = None

    @classmethod
    def get_or_fit_pipeline(
        cls,
        db: Optional[Session] = None,
        learner_type: CounterfactualLearnerType = CounterfactualLearnerType.DOUBLY_ROBUST_LEARNER,
        force_refit: bool = False,
    ) -> CounterfactualLearnerPipeline:
        """Retrieves or trains the counterfactual learner pipeline."""
        if cls._cached_pipeline is not None and not force_refit and cls._cached_pipeline.learner_type == learner_type:
            return cls._cached_pipeline

        # Extract data from DB if available; fallback to benchmark observational study
        training_df = pd.DataFrame()
        if db is not None:
            training_df = CounterfactualDatasetBuilder.extract_intervention_records_from_db(db=db, limit=300)

        if len(training_df) < 50:
            training_df = CounterfactualDatasetBuilder.generate_benchmark_counterfactual_dataset(
                n_samples=350,
                seed=42,
            )

        pipeline = CounterfactualLearnerPipeline(learner_type=learner_type)
        pipeline.fit(training_df)
        cls._cached_pipeline = pipeline
        return pipeline

    @classmethod
    def compare_interventions(
        cls,
        db: Session,
        request: CounterfactualComparisonRequest,
    ) -> CounterfactualComparisonResponse:
        """
        Compares all plausible intervention alternatives for a target context.
        Ranks candidates by multi-objective counterfactual uplift and provides
        explicit fallback when counterfactual conditions are not satisfied.
        """
        pipeline = cls.get_or_fit_pipeline(db=db, learner_type=request.learner)

        # 1. Resolve context features
        features = dict(request.context_features or {})
        user_id = request.user_id or uuid.uuid4()
        task_id = request.task_id

        # If a task_id was supplied, enrich features from task state
        if task_id is not None:
            task = db.get(Task, task_id)
            if task:
                features.setdefault("task_priority", float(getattr(task, "priority_score", 3.0) or 3.0))
                features.setdefault("forgetting_risk", float(getattr(task, "forgetting_risk", 0.45) or 0.45))
                features.setdefault("baseline_bfi", float(getattr(task, "baseline_bfi", 50.0) or 50.0))

        # Default fallbacks
        features.setdefault("baseline_bfi", 52.0)
        features.setdefault("forgetting_risk", 0.45)
        features.setdefault("task_priority", 3.0)
        features.setdefault("calendar_load", 3.5)
        features.setdefault("recent_interruptions", 3.0)

        # 2. Evaluate all candidates
        candidate_results = pipeline.evaluate_candidates(context_features=features)

        # 3. Decisioning & Fallback Check
        # Filter to supported candidates with positive uplift
        supported_candidates = [
            c for c in candidate_results
            if c.is_supported and c.candidate != CandidateIntervention.NO_INTERVENTION
        ]

        champion_candidate: Optional[CandidateIntervention] = None
        strategy = RecommendationStrategy.DETERMINISTIC_FALLBACK
        fallback_reason: Optional[str] = None

        if not supported_candidates:
            fallback_reason = "No candidate intervention met minimum data coverage and overlap criteria. Falling back to deterministic rules."
            # Fallback heuristic: choose recovery buffer if friction > 60, else reminder
            if features.get("baseline_bfi", 0.0) > 60.0:
                champion_candidate = CandidateIntervention.SHORT_RECOVERY_BUFFER
            else:
                champion_candidate = CandidateIntervention.IMMEDIATE_REMINDER
        else:
            # Sort by composite uplift score
            supported_candidates.sort(key=lambda x: x.composite_uplift_score or -999.0, reverse=True)
            top_candidate = supported_candidates[0]

            # Check uncertainty tolerance
            # e.g. check width of completion or resumption interval
            res_interval = top_candidate.uncertainty_intervals.get("task_resumption_probability", (0.0, 1.0))
            interval_width = res_interval[1] - res_interval[0]

            if interval_width > request.strict_uncertainty_threshold:
                strategy = RecommendationStrategy.DETERMINISTIC_FALLBACK
                fallback_reason = (
                    f"Top candidate ({top_candidate.title}) uncertainty interval width ({interval_width:.2f}) "
                    f"exceeds tolerance ({request.strict_uncertainty_threshold:.2f}). Reverting to deterministic baseline."
                )
                champion_candidate = CandidateIntervention.SHORT_RECOVERY_BUFFER
            elif (top_candidate.composite_uplift_score or 0.0) <= 0.0:
                strategy = RecommendationStrategy.DETERMINISTIC_FALLBACK
                fallback_reason = "No candidate demonstrates positive incremental utility over passive holdout. Withholding active intervention."
                champion_candidate = CandidateIntervention.NO_INTERVENTION
            else:
                strategy = RecommendationStrategy.COUNTERFACTUAL_OPTIMIZED
                champion_candidate = top_candidate.candidate
                fallback_reason = None

        return CounterfactualComparisonResponse(
            context_id=f"cf_ctx_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            evaluation_timestamp=datetime.now(timezone.utc),
            target_task_id=task_id,
            baseline_candidate=CandidateIntervention.NO_INTERVENTION,
            candidates=candidate_results,
            recommended_champion=champion_candidate,
            recommendation_source=strategy,
            fallback_reason=fallback_reason,
        )
