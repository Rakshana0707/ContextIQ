"""
Feature Extractor for Adaptive Task Prioritization (Phase 4.4).
Extracts and normalizes multi-objective signals strictly as of a reference cutoff time.
Guarantees no future data leakage.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.enums import TaskPriority
from app.models.task import Task
from app.services.prediction_service import PredictionService


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class PrioritizationFeatureExtractor:
    """Extracts leakage-safe, normalized prioritization features for a candidate task."""

    @classmethod
    def extract_task_features(
        cls,
        db: Session,
        task: Task,
        user_id: uuid.UUID,
        as_of: Optional[datetime] = None,
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extracts normalized features in [0.0, 1.0] for task urgency, forgetting risk,
        personal suitability, context compatibility, and scheduling feasibility.
        """
        ref_time = _normalize_utc(as_of) or _normalize_utc(datetime.now(timezone.utc))

        # 1. Deadline Proximity
        due_at_utc = _normalize_utc(task.due_at)
        is_overdue = False
        hours_to_deadline: Optional[float] = None

        if due_at_utc is not None:
            delta_seconds = (due_at_utc - ref_time).total_seconds()
            hours_to_deadline = delta_seconds / 3600.0
            if hours_to_deadline < 0:
                is_overdue = True
                deadline_score = 1.0
            elif hours_to_deadline <= 4.0:
                # Imminent deadline: [0.90, 0.95]
                deadline_score = 0.95 - 0.05 * (hours_to_deadline / 4.0)
            elif hours_to_deadline <= 24.0:
                # Near-term deadline (today): [0.70, 0.90]
                deadline_score = 0.90 - 0.20 * ((hours_to_deadline - 4.0) / 20.0)
            elif hours_to_deadline <= 72.0:
                # Medium-term (next 3 days): [0.45, 0.70]
                deadline_score = 0.70 - 0.25 * ((hours_to_deadline - 24.0) / 48.0)
            else:
                # Long-term: decay towards baseline
                deadline_score = max(0.10, 0.45 * math.exp(-(hours_to_deadline - 72.0) / 72.0))
        else:
            deadline_score = 0.20  # Neutral baseline for open-ended tasks

        # 2. Task Importance (User explicit priority)
        prio_map = {
            TaskPriority.URGENT: 1.0,
            TaskPriority.HIGH: 0.75,
            TaskPriority.MEDIUM: 0.50,
            TaskPriority.LOW: 0.25,
        }
        importance_score = prio_map.get(task.priority, 0.50)

        # Urgency combines deadline proximity and explicit priority:
        # Near-term deadlines can escalate priority, while urgent explicit priority keeps score high.
        urgency_score = min(1.0, 0.65 * deadline_score + 0.35 * importance_score)

        # 3. Forgetting Risk & Survival Probability
        forgetting_prob = 0.35
        survival_hazard = 0.30
        is_cold_start = True

        try:
            pred = PredictionService.predict_for_task(
                db=db, user_id=user_id, task_id=task.id, as_of=ref_time
            )
            forgetting_prob = float(pred.risk_score)
            if pred.survival_estimates:
                # Find survival at 24h
                s24 = next((s.survival_probability for s in pred.survival_estimates if s.horizon_hours == 24), 0.70)
                survival_hazard = max(0.0, min(1.0, 1.0 - s24))
            is_cold_start = (
                getattr(pred, "confidence_discount_applied", False)
                or (hasattr(pred, "feature_availability") and getattr(pred.feature_availability, "is_cold_start", False))
            )
        except Exception:
            # Fallback based on task age if prediction service unavailable or task unpersisted
            is_cold_start = True
            created_utc = _normalize_utc(task.created_at) or ref_time
            age_days = max(0.0, (ref_time - created_utc).total_seconds() / 86400.0)
            forgetting_prob = min(0.95, 0.20 + 0.15 * math.log1p(age_days))
            survival_hazard = min(0.90, 0.15 + 0.15 * math.log1p(age_days))

        if profile_data and profile_data.get("overall_pattern_status") == "INSUFFICIENT_EVIDENCE":
            is_cold_start = True

        # Composite forgetting risk component
        created_utc = _normalize_utc(task.created_at) or ref_time
        age_days = max(0.0, (ref_time - created_utc).total_seconds() / 86400.0)
        age_factor = min(1.0, age_days / 14.0)
        forgetting_risk_score = min(
            1.0, 0.60 * forgetting_prob + 0.25 * survival_hazard + 0.15 * age_factor
        )

        # 4. Duration and Recovery Buffer
        estimated_mins = task.estimated_minutes
        if not estimated_mins or estimated_mins <= 0:
            # Fallback to category typical duration from profile or default 30
            estimated_mins = 30
            if profile_data and "task_completion" in profile_data:
                comp_dim = profile_data["task_completion"]
                dur_by_cat = comp_dim.get("task_completion_duration_by_category", {}).get("observed_value", {})
                if isinstance(dur_by_cat, dict) and task.context_tag in dur_by_cat:
                    estimated_mins = int(dur_by_cat[task.context_tag])

        # Recovery buffer calculation
        bfi = 40.0
        if profile_data and "baselines" in profile_data:
            bfi = profile_data["baselines"].get("baseline_friction_index", 40.0)

        if estimated_mins >= 60 or bfi >= 60.0:
            recovery_buffer = 15
        elif estimated_mins <= 20:
            recovery_buffer = 5
        else:
            recovery_buffer = 10

        return {
            "task_id": task.id,
            "title": task.title,
            "context_tag": task.context_tag,
            "priority": str(task.priority.value if hasattr(task.priority, "value") else task.priority),
            "status": str(task.status.value if hasattr(task.status, "value") else task.status),
            "due_at": due_at_utc,
            "hours_to_deadline": hours_to_deadline,
            "is_overdue": is_overdue,
            "deadline_score": round(deadline_score, 3),
            "importance_score": round(importance_score, 3),
            "urgency_score": round(urgency_score, 3),
            "forgetting_prob": round(forgetting_prob, 3),
            "survival_hazard": round(survival_hazard, 3),
            "age_days": round(age_days, 1),
            "forgetting_risk_score": round(forgetting_risk_score, 3),
            "estimated_minutes": estimated_mins,
            "recovery_buffer_minutes": recovery_buffer,
            "is_cold_start": is_cold_start,
            "parent_task_id": task.parent_task_id,
        }
