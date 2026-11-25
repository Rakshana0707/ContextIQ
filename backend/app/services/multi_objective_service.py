"""
High-Level Multi-Objective Optimization Service (ContextIQ Phase 6.7).

Coordinates:
- Extraction of user preferences, notification limits, and quiet hours from database.
- Enforcement of safety boundaries: Proposal-only recommendations requiring user consent.
- User-customizable objective weights and constraint management.
- Transparent reporting of objectives, constraints, and optimization trade-offs.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_models import UserNotification, UserNotificationPreference
from app.models.task import Task
from app.schemas.counterfactual import CandidateIntervention
from app.schemas.multi_objective_optimization import (
    HardConstraintType,
    MultiObjectiveOptimizationRequest,
    MultiObjectiveOptimizationResponse,
    ObjectiveWeights,
    OptimizationObjective,
    UserOptimizationPreferences,
)
from app.services.multi_objective_optimizer import MultiObjectiveOptimizer

logger = logging.getLogger(__name__)


class MultiObjectiveService:
    """
    High-level service coordinating multi-objective intervention optimization.
    """

    _user_preferences_store: Dict[uuid.UUID, UserOptimizationPreferences] = {}

    @classmethod
    def list_objectives(cls) -> List[Dict[str, Any]]:
        """Lists all 8 optimization objectives with direction, descriptions, and default weights."""
        return [
            {
                "id": OptimizationObjective.TASK_COMPLETION.value,
                "title": "Task Completion Likelihood",
                "direction": "maximize",
                "default_weight": 0.20,
                "description": "Probability that the current task is completed on or before scheduled deadline.",
            },
            {
                "id": OptimizationObjective.TASK_RESUMPTION.value,
                "title": "Task Resumption Likelihood",
                "direction": "maximize",
                "default_weight": 0.15,
                "description": "Probability of deliberate, grounded task resumption within 15 minutes of disruption.",
            },
            {
                "id": OptimizationObjective.RECOVERY_DURATION.value,
                "title": "Cognitive Recovery Speed",
                "direction": "maximize",
                "default_weight": 0.15,
                "description": "Speed of cognitive recovery and restoration of working memory efficiency.",
            },
            {
                "id": OptimizationObjective.BEHAVIORAL_FRICTION.value,
                "title": "Cognitive Friction Reduction",
                "direction": "maximize",
                "default_weight": 0.15,
                "description": "Reduction of mental fatigue and micro-delay friction (100 - BFI score).",
            },
            {
                "id": OptimizationObjective.NOTIFICATION_ECONOMY.value,
                "title": "Notification Economy",
                "direction": "maximize",
                "default_weight": 0.15,
                "description": "Minimization of alert disruption and psychological notification burden.",
            },
            {
                "id": OptimizationObjective.INTERRUPTION_COMFORT.value,
                "title": "Interruption Comfort",
                "direction": "maximize",
                "default_weight": 0.10,
                "description": "Preservation of sustained attention and avoidance of disruptive task breaks.",
            },
            {
                "id": OptimizationObjective.USER_PREFERENCES.value,
                "title": "User Preference Alignment",
                "direction": "maximize",
                "default_weight": 0.05,
                "description": "Explicit user affinity and alignment with configured intervention settings.",
            },
            {
                "id": OptimizationObjective.SCHEDULE_FEASIBILITY.value,
                "title": "Schedule Feasibility",
                "direction": "maximize",
                "default_weight": 0.05,
                "description": "Calendar buffer availability, slack time, and conflict-free execution window.",
            },
        ]

    @classmethod
    def list_constraints(cls) -> List[Dict[str, Any]]:
        """Lists all 7 non-bypassable hard constraints and gating mechanisms."""
        return [
            {
                "id": HardConstraintType.QUIET_HOURS.value,
                "title": "User Quiet Hours",
                "gating_rule": "Notification alerts (audible or visual) are prohibited during configured quiet windows.",
                "bypassable": False,
            },
            {
                "id": HardConstraintType.MAX_NOTIFICATION_FREQUENCY.value,
                "title": "Notification Quota Limits",
                "gating_rule": "Exceeding hourly or daily notification caps strictly suppresses active alerts.",
                "bypassable": False,
            },
            {
                "id": HardConstraintType.CALENDAR_AVAILABILITY.value,
                "title": "Calendar Availability",
                "gating_rule": "Calendar rescheduling and focus sessions require conflict-free availability slots.",
                "bypassable": False,
            },
            {
                "id": HardConstraintType.WORKING_HOURS.value,
                "title": "User-Defined Working Hours",
                "gating_rule": "Interventions cannot schedule professional tasks outside configured working hours.",
                "bypassable": False,
            },
            {
                "id": HardConstraintType.EXPLICIT_TASK_CONSTRAINTS.value,
                "title": "Task Immutability & Deadlines",
                "gating_rule": "Tasks with imminent deadlines (<15m) or immutability flags cannot be postponed.",
                "bypassable": False,
            },
            {
                "id": HardConstraintType.CONSENT_AND_PERMISSIONS.value,
                "title": "Consent & Channel Permissions",
                "gating_rule": "Revoked channel permissions immediately invalidate associated intervention channels.",
                "bypassable": False,
            },
            {
                "id": HardConstraintType.USER_OPT_OUT.value,
                "title": "User Opt-Out Settings",
                "gating_rule": "Explicit user opt-outs for specific intervention types are strictly respected.",
                "bypassable": False,
            },
        ]

    @classmethod
    def optimize_intervention(
        cls,
        db: Session,
        request: MultiObjectiveOptimizationRequest,
    ) -> MultiObjectiveOptimizationResponse:
        """
        Coordinates full optimization flow: extracts DB context, enriches constraints,
        and delegates to MultiObjectiveOptimizer.
        """
        user_id = request.user_id or uuid.uuid4()
        now = request.current_time or datetime.now(timezone.utc)

        # 1. Enrich context features and constraints from DB
        enriched_features = dict(request.context_features or {})
        enriched_constraints = dict(request.user_constraints or {})

        # Extract notification preferences if available
        try:
            stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
            pref = db.execute(stmt).scalars().first()
            if pref:
                enriched_constraints.setdefault("quiet_hours_enabled", pref.quiet_hours_enabled)
                enriched_constraints.setdefault("quiet_hours_start", pref.quiet_hours_start)
                enriched_constraints.setdefault("quiet_hours_end", pref.quiet_hours_end)
                enriched_constraints.setdefault("max_notifications_per_day", pref.max_notifications_per_day)
                enriched_constraints.setdefault("max_notifications_per_hour", pref.max_notifications_per_hour)
                enriched_constraints.setdefault("notifications_permitted", not pref.is_paused)
        except Exception as e:
            logger.debug("Could not query notification preferences: %s", e)

        # Extract task metadata if provided
        if request.task_id is not None:
            try:
                task = db.get(Task, request.task_id)
                if task:
                    enriched_features.setdefault("task_priority", float(getattr(task, "priority_score", 3.0) or 3.0))
                    if task.due_at:
                        diff_minutes = (task.due_at - now).total_seconds() / 60.0
                        enriched_features.setdefault("due_in_minutes", max(0.0, diff_minutes))
            except Exception as e:
                logger.debug("Could not query task: %s", e)

        # Apply stored user customization preferences if not explicitly overridden
        custom_weights = request.custom_weights
        if custom_weights is None and user_id in cls._user_preferences_store:
            stored = cls._user_preferences_store[user_id]
            custom_weights = stored.preferred_weights
            enriched_constraints.setdefault("opted_out_interventions", stored.opted_out_interventions)

        # Create enriched request
        enriched_request = MultiObjectiveOptimizationRequest(
            user_id=user_id,
            task_id=request.task_id,
            current_time=now,
            context_features=enriched_features,
            custom_weights=custom_weights,
            user_constraints=enriched_constraints,
            strict_uncertainty_threshold=request.strict_uncertainty_threshold,
            min_utility_lift_threshold=request.min_utility_lift_threshold,
        )

        return MultiObjectiveOptimizer.optimize(enriched_request)

    @classmethod
    def get_user_preferences(
        cls,
        user_id: uuid.UUID,
    ) -> UserOptimizationPreferences:
        """Retrieves user's custom optimization weights and preferences or defaults."""
        if user_id not in cls._user_preferences_store:
            cls._user_preferences_store[user_id] = UserOptimizationPreferences(
                user_id=user_id,
                preferred_weights=ObjectiveWeights(),
                opted_out_interventions=[],
            )
        return cls._user_preferences_store[user_id]

    @classmethod
    def update_user_preferences(
        cls,
        preferences: UserOptimizationPreferences,
    ) -> UserOptimizationPreferences:
        """Updates user's custom objective weights and opt-outs."""
        preferences.preferred_weights = preferences.preferred_weights.normalized()
        preferences.updated_at = datetime.now(timezone.utc)
        cls._user_preferences_store[preferences.user_id] = preferences
        return preferences
