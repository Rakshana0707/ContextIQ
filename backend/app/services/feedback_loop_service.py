"""
Feedback Loop & Continuous Calibration Service (Phase 3.8).

Aggregates user feedback from:
1. Detected interruption ground-truth validations (DetectedInterruptionFeedback).
2. Recommendation acceptance/rejections (RecommendationFeedback).
3. Task lifecycle outcomes (Completed vs Forgotten).

Safety Policy:
- Immutable audit records.
- STRICTLY PROHIBITS automated in-flight retraining of unvalidated models in production.
- Exports validated candidate training datasets for offline human review, evaluation, and calibration.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detected_interruption import DetectedInterruption, DetectedInterruptionFeedback
from app.models.enums import TaskStatus
from app.models.prediction import Prediction
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.task import Task
from app.services.temporal_feature_extractor import TemporalFeatureExtractor

logger = logging.getLogger(__name__)


class FeedbackLoopService:
    """Manages ground-truth feedback integration and offline calibration datasets."""

    AUTO_RETRAIN_ALLOWED: bool = False  # Strict safety guarantee: no live auto-retraining

    @classmethod
    def export_candidate_training_dataset(
        cls,
        db: Session,
        user_id: Optional[uuid.UUID] = None,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Gathers user-validated interruption feedback, recommendation responses,
        and task outcomes alongside their leakage-safe features as-of the event.
        """
        now_utc = as_of or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # 1. Gather interruption ground truth feedback
        int_stmt = select(DetectedInterruptionFeedback)
        if user_id:
            int_stmt = int_stmt.where(DetectedInterruptionFeedback.user_id == user_id)
        feedbacks = list(db.scalars(int_stmt).all())

        interruption_samples: List[Dict[str, Any]] = []
        for fb in feedbacks:
            parent = db.get(DetectedInterruption, fb.interruption_id)
            if parent:
                interruption_samples.append({
                    "feedback_id": str(fb.id),
                    "interruption_id": str(fb.interruption_id),
                    "user_id": str(fb.user_id),
                    "interruption_type": parent.interruption_type.value,
                    "duration_seconds": parent.duration_seconds,
                    "resumption_lag_observed": parent.resumption_lag_seconds,
                    "ground_truth_classification": fb.feedback_classification.value,
                    "notes": fb.notes,
                    "timestamp": fb.created_at.isoformat() if fb.created_at else None,
                })

        # 2. Gather task forgetting outcomes
        task_stmt = select(Task).where(
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FORGOTTEN])
        )
        if user_id:
            task_stmt = task_stmt.where(Task.user_id == user_id)
        tasks = list(db.scalars(task_stmt).all())

        task_outcome_samples: List[Dict[str, Any]] = []
        for t in tasks:
            # Fetch latest prediction created prior to task resolution
            pred_stmt = (
                select(Prediction)
                .where(Prediction.task_id == t.id)
                .order_by(Prediction.created_at.desc())
                .limit(1)
            )
            pred = db.scalar(pred_stmt)

            # Extract leakage-safe features as-of task creation
            ref_t = t.created_at or now_utc
            try:
                features_as_of = TemporalFeatureExtractor.extract_features_for_task(
                    db=db, user_id=t.user_id, as_of=ref_t
                )
            except Exception:
                features_as_of = {}

            actual_forgotten = 1 if t.status == TaskStatus.FORGOTTEN else 0
            task_outcome_samples.append({
                "task_id": str(t.id),
                "user_id": str(t.user_id),
                "title": t.title,
                "context_tag": t.context_tag,
                "actual_outcome": t.status.value,
                "label_forgotten": actual_forgotten,
                "predicted_risk_probability": pred.confidence if pred else None,
                "predicted_model_version": pred.model_version if pred else None,
                "features_as_of_creation": features_as_of,
                "resolved_at": t.updated_at.isoformat() if hasattr(t, "updated_at") and t.updated_at else None,
            })

        # 3. Gather recommendation feedback
        rec_stmt = select(RecommendationFeedback)
        if user_id:
            rec_stmt = rec_stmt.where(RecommendationFeedback.user_id == user_id)
        rec_feedbacks = list(db.scalars(rec_stmt).all())

        recommendation_samples = [
            {
                "feedback_id": str(rf.id),
                "recommendation_id": str(rf.recommendation_id),
                "user_id": str(rf.user_id),
                "action": rf.action.value,
                "note": rf.feedback_note,
                "created_at": rf.created_at.isoformat() if rf.created_at else None,
            }
            for rf in rec_feedbacks
        ]

        total_samples = len(interruption_samples) + len(task_outcome_samples) + len(recommendation_samples)

        return {
            "dataset_version": "candidate-v2.3",
            "extracted_at": now_utc.isoformat(),
            "auto_retraining_allowed": cls.AUTO_RETRAIN_ALLOWED,
            "policy": "Requires offline statistical validation & human review before registry promotion.",
            "total_candidate_samples": total_samples,
            "interruption_feedback_samples": interruption_samples,
            "task_outcome_samples": task_outcome_samples,
            "recommendation_feedback_samples": recommendation_samples,
        }
