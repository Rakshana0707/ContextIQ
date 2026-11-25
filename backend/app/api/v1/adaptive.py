"""
FastAPI router for ContextIQ Personal Behavioral Digital Twin & Adaptive Intelligence (Phase 4.2).
Provides authenticated endpoints for profile inspection, historical snapshots,
rebuilds, resets, personalization toggles, and deletion.
"""
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id, get_db
from app.schemas.adaptive import (
    DigitalTwinProfileRead,
    PersonalizationToggleRequest,
    PersonalizationToggleResponse,
    ProfileResetResponse,
    ProfileSnapshotRead,
)
from app.schemas.focus_window import (
    CategoryFocusWindowRead,
    FocusWindowItemRead,
    FocusWindowMetricsResponse,
)
from app.schemas.task_ranking import (
    TaskRankingResponse,
    TaskRankingPreviewRequest,
    TaskRankingFeedbackCreate,
    TaskRankingFeedbackRead,
)
from app.schemas.intervention_schemas import (
    InterventionActionRequest,
    InterventionGenerateRequest,
    InterventionRead,
)
from app.schemas.bandit_schemas import (
    BanditFeedbackRequest,
    BanditFeedbackResponse,
    BanditMetricsResponse,
    BanditPolicyResponse,
    BanditSelectRequest,
    BanditSelectResponse,
)
from app.schemas.effectiveness_schemas import (
    InterventionEffectivenessOverview,
    InterventionExperimentRead,
    InterventionOutcomeRead,
    InterventionTypeComparison,
)
from app.schemas.notification_schemas import (
    NotificationAcknowledgeResponse,
    NotificationCreateRequest,
    NotificationDismissRequest,
    NotificationDismissResponse,
    NotificationMetricsResponse,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
)
from app.services.adaptive.profile_service import AdaptiveProfileService


router = APIRouter(prefix="/adaptive", tags=["adaptive"])


@router.get(
    "/profile",
    response_model=DigitalTwinProfileRead,
    summary="Get Personal Behavioral Digital Twin Profile",
    description="Returns the active empirical behavioral profile with confidence levels and data provenance.",
)
def get_personal_behavioral_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AdaptiveProfileService.get_profile(db=db, user_id=user_id)


@router.get(
    "/profile/history",
    response_model=List[ProfileSnapshotRead],
    summary="Get Versioned Profile Snapshot History",
    description="Returns immutable historical snapshots of the user's behavioral digital twin.",
)
def get_profile_history(
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AdaptiveProfileService.get_history(db=db, user_id=user_id, limit=limit)


@router.post(
    "/profile/rebuild",
    response_model=DigitalTwinProfileRead,
    summary="Rebuild Profile from Historical Data",
    description="Performs an authoritative recalculation of all dimensions strictly prior to as_of cutoff.",
)
def rebuild_personal_profile(
    as_of: Optional[datetime] = None,
    observation_window_days: int = Query(30, ge=1, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AdaptiveProfileService.rebuild_profile(
        db=db,
        user_id=user_id,
        as_of=as_of,
        observation_window_days=observation_window_days,
    )


@router.post(
    "/profile/reset",
    response_model=ProfileResetResponse,
    summary="Reset Personal Behavioral Profile",
    description="Purges empirical observations and reverts the profile to prior cold-start defaults.",
)
def reset_personal_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AdaptiveProfileService.reset_profile(db=db, user_id=user_id)


@router.put(
    "/profile/personalization",
    response_model=PersonalizationToggleResponse,
    summary="Toggle Adaptive Personalization",
    description="Enables or disables behavioral personalization and adaptive interventions.",
)
def toggle_personalization(
    payload: PersonalizationToggleRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = AdaptiveProfileService.set_personalization(db=db, user_id=user_id, enabled=payload.enabled)
    return PersonalizationToggleResponse(
        status="SUCCESS",
        personalization_enabled=profile.personalization_enabled,
        user_id=user_id,
        updated_at=profile.updated_at,
    )


@router.delete(
    "/profile",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Behavioral Profile (Right to be Forgotten)",
    description="Hard deletes all profile dimensions, historical snapshots, and audit records for the user.",
)
def delete_personal_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.profiles.profile_repository import ProfileRepository
    ProfileRepository.delete_profile(db, user_id)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Phase 4.3: Focus-Window Discovery Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/focus-windows",
    response_model=List[FocusWindowItemRead],
    summary="List Discovered Focus Windows",
    description="Returns verified personal productivity intervals and cadences for the user.",
)
def get_focus_windows(
    category: Optional[str] = Query(None, description="Optional task category filter"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    force_refresh: bool = Query(False, description="Trigger fresh discovery instead of reading cached windows"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.focus_window_service import FocusWindowService
    return FocusWindowService.get_or_discover_windows(
        db=db,
        user_id=user_id,
        category=category,
        min_confidence=min_confidence,
        force_refresh=force_refresh,
    )


@router.get(
    "/focus-windows/metrics",
    response_model=FocusWindowMetricsResponse,
    summary="Get 24-Hour Circadian Focus Metrics",
    description="Returns hourly metric distribution across focus duration, completion rate, disruptions, and latency.",
)
def get_focus_metrics(
    observation_window_days: int = Query(30, ge=1, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.focus_window_service import FocusWindowService
    return FocusWindowService.get_hourly_metrics(
        db=db,
        user_id=user_id,
        observation_window_days=observation_window_days,
    )


@router.get(
    "/focus-windows/{category}",
    response_model=CategoryFocusWindowRead,
    summary="Get Category-Conditioned Focus Windows",
    description="Returns focus windows conditioned specifically on a task category with completion lift metrics.",
)
def get_category_focus_windows(
    category: str,
    observation_window_days: int = Query(30, ge=1, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.focus_window_service import FocusWindowService
    return FocusWindowService.get_category_focus_windows(
        db=db,
        user_id=user_id,
        category=category,
        observation_window_days=observation_window_days,
    )


# ---------------------------------------------------------------------------
# Phase 4.4: Adaptive Task Prioritization & Scheduling Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/task-ranking",
    response_model=TaskRankingResponse,
    summary="Get Adaptive Task Ranking",
    description="Returns personalized, explainable task priorities conditioned on urgency, forgetting risk, focus windows, and context.",
)
def get_task_ranking(
    as_of: Optional[datetime] = Query(None, description="Optional reference cutoff timestamp"),
    context_tag: Optional[str] = Query(None, description="Optional active work context tag"),
    preset: Optional[str] = Query("BALANCED", description="BALANCED, DEEP_WORK, DEADLINE_CRUNCH, RECOVERY_MODE"),
    include_blocked: bool = Query(True, description="Whether to include tasks blocked by parent dependencies"),
    limit: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.ranking_service import AdaptiveRankingService
    return AdaptiveRankingService.get_task_ranking(
        db=db,
        user_id=user_id,
        as_of=as_of,
        current_context_tag=context_tag,
        preset=preset,
        include_blocked=include_blocked,
        limit=limit,
    )


@router.post(
    "/task-ranking/preview",
    response_model=TaskRankingResponse,
    summary="Simulate Hypothetical Task Ranking",
    description="Simulates task ranking under specified temporal, contextual, or weight overrides without persisting state.",
)
def preview_task_ranking(
    request: TaskRankingPreviewRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.ranking_service import AdaptiveRankingService
    return AdaptiveRankingService.preview_task_ranking(
        db=db,
        user_id=user_id,
        request=request,
    )


@router.post(
    "/task-ranking/feedback",
    response_model=TaskRankingFeedbackRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Task Ranking Feedback / Override",
    description="Records explicit user actions (ACCEPTED, SNOOZED, PINNED, DISMISSED, REORDERED) on task recommendations.",
)
def record_task_ranking_feedback(
    feedback_in: TaskRankingFeedbackCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.ranking_service import AdaptiveRankingService
    return AdaptiveRankingService.record_feedback(
        db=db,
        user_id=user_id,
        feedback_in=feedback_in,
    )


# ---------------------------------------------------------------------------
# Phase 4.5: Personalized Intervention Recommendation Engine Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/interventions",
    response_model=List[InterventionRead],
    summary="Get Personalized Interventions",
    description="Returns active, unexpired, non-deferred behavioral interventions tailored to the user's empirical context.",
)
def get_personalized_interventions(
    status: Optional[str] = Query(None, description="Optional status filter (e.g. GENERATED, PRESENTED, ACCEPTED, DISMISSED, DEFERRED, EXPIRED)"),
    category: Optional[str] = Query(None, description="Optional category filter (FOCUS, RECOVERY, TASK, CONTEXTUAL, WORKLOAD)"),
    include_deferred: bool = Query(False, description="Whether to include currently deferred recommendations"),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.intervention_service import InterventionService
    return InterventionService.get_interventions(
        db=db,
        user_id=user_id,
        status_filter=status,
        category=category,
        include_deferred=include_deferred,
        limit=limit,
    )


@router.post(
    "/interventions/generate",
    response_model=List[InterventionRead],
    summary="Generate Grounded Interventions",
    description="Evaluates empirical behavioral telemetry, tasks, and focus windows to generate grounded, deduplicated recommendations.",
)
def generate_personalized_interventions(
    request: Optional[InterventionGenerateRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.intervention_service import InterventionService
    return InterventionService.generate_interventions(
        db=db,
        user_id=user_id,
        request=request,
    )


@router.post(
    "/interventions/{intervention_id}/accept",
    response_model=InterventionRead,
    summary="Accept Intervention Recommendation",
    description="Transitions intervention to ACCEPTED and records user agreement for continuous reinforcement.",
)
def accept_intervention(
    intervention_id: uuid.UUID,
    action: Optional[InterventionActionRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.intervention_service import InterventionService
    return InterventionService.accept_intervention(
        db=db,
        user_id=user_id,
        intervention_id=intervention_id,
        action=action,
    )


@router.post(
    "/interventions/{intervention_id}/dismiss",
    response_model=InterventionRead,
    summary="Dismiss Intervention Recommendation",
    description="Transitions intervention to DISMISSED with optional feedback note, gently damping repetition.",
)
def dismiss_intervention(
    intervention_id: uuid.UUID,
    action: Optional[InterventionActionRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.intervention_service import InterventionService
    return InterventionService.dismiss_intervention(
        db=db,
        user_id=user_id,
        intervention_id=intervention_id,
        action=action,
    )


@router.post(
    "/interventions/{intervention_id}/defer",
    response_model=InterventionRead,
    summary="Defer Intervention Recommendation",
    description="Postpones presentation of the intervention until deferred_until passes.",
)
def defer_intervention(
    intervention_id: uuid.UUID,
    action: Optional[InterventionActionRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.intervention_service import InterventionService
    return InterventionService.defer_intervention(
        db=db,
        user_id=user_id,
        intervention_id=intervention_id,
        action=action,
    )


# ---------------------------------------------------------------------------
# Phase 4.6: Contextual Bandit Learning Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/bandit/select",
    response_model=BanditSelectResponse,
    summary="Select Intervention via Contextual Bandit",
    description="Evaluates context vector x_t and selects optimal intervention arm using LinUCB or Thompson Sampling.",
)
def select_bandit_intervention(
    request: Optional[BanditSelectRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.bandit_service import BanditService
    return BanditService.select_intervention(db=db, user_id=user_id, request=request)


@router.post(
    "/bandit/feedback",
    response_model=BanditFeedbackResponse,
    summary="Record Bandit Decision Feedback",
    description="Ingests explicit feedback and subsequent behavioral telemetry, synthesizing composite reward R_t and updating arm parameters.",
)
def record_bandit_feedback(
    request: BanditFeedbackRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.bandit_service import BanditService
    return BanditService.record_feedback(db=db, user_id=user_id, request=request)


@router.get(
    "/bandit/metrics",
    response_model=BanditMetricsResponse,
    summary="Get Contextual Bandit Performance Metrics",
    description="Returns aggregate reward statistics, arm pull distributions, and circuit breaker statuses.",
)
def get_bandit_metrics(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.bandit_service import BanditService
    return BanditService.get_metrics(db=db, user_id=user_id)


@router.get(
    "/bandit/policy",
    response_model=BanditPolicyResponse,
    summary="Get Contextual Bandit Policy Configuration",
    description="Returns active algorithm parameters, feature dimension, quiet periods, and registered arms.",
)
def get_bandit_policy(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.bandit_service import BanditService
    return BanditService.get_policy(db=db, user_id=user_id)


# ============================================================================
# Phase 4.7: Intervention Effectiveness & Causal Evaluation
# ============================================================================


@router.get(
    "/effectiveness/overview",
    response_model=InterventionEffectivenessOverview,
    summary="Get Intervention Effectiveness Overview",
    description="Calculates overall acceptance vs. execution rates, cognitive improvements, and estimated causal ATE.",
)
def get_effectiveness_overview(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.effectiveness_service import EffectivenessService
    return EffectivenessService.get_overview(db=db, user_id=user_id)


@router.get(
    "/effectiveness/interventions",
    response_model=List[InterventionTypeComparison],
    summary="Get Comparative Intervention Effectiveness",
    description="Returns comparative breakdown across intervention types with Doubly Robust ATE, 95% CIs, and habituation fatigue flags.",
)
def get_interventions_effectiveness(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.effectiveness_service import EffectivenessService
    return EffectivenessService.get_interventions_comparison(db=db, user_id=user_id)


@router.get(
    "/effectiveness/experiments",
    response_model=List[InterventionExperimentRead],
    summary="Get Active Randomized Holdout Experiments",
    description="Lists active randomized controlled holdout experiments and sample distributions.",
)
def get_effectiveness_experiments(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.effectiveness_service import EffectivenessService
    return EffectivenessService.get_experiments(db=db, user_id=user_id)


@router.get(
    "/effectiveness/{intervention_id}",
    response_model=InterventionOutcomeRead,
    summary="Get Single Intervention Outcome",
    description="Retrieves granular multi-horizon outcome record, baseline vs. observed deltas, and execution evidence for an intervention.",
)
def get_intervention_outcome(
    intervention_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.effectiveness_service import EffectivenessService
    return EffectivenessService.get_outcome_by_id(db=db, user_id=user_id, outcome_or_intervention_id=intervention_id)


# ============================================================================
# Phase 4.8: Intelligent Notification & Cognitive Load Management
# ============================================================================


@router.get(
    "/notifications",
    response_model=List[NotificationRead],
    summary="Get User Notifications",
    description="Retrieves notifications for the authenticated user with optional filtering by unread status or category.",
)
def get_user_notifications(
    unread_only: bool = Query(False, description="Filter for unread/non-dismissed notifications only"),
    category: Optional[str] = Query(None, description="Filter by notification category"),
    limit: int = Query(50, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    return NotificationService.list_notifications(
        db=db, user_id=user_id, unread_only=unread_only, category=category, limit=limit
    )


@router.post(
    "/notifications",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Schedule Notification",
    description="Evaluates cognitive shielding eligibility and dispatches or defers a candidate notification.",
)
def create_user_notification(
    request: NotificationCreateRequest,
    is_in_active_focus_session: bool = Query(False, description="Whether user is currently in a deep work focus session"),
    focus_remaining_minutes: Optional[int] = Query(None, description="Remaining minutes in current focus session"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    return NotificationService.schedule_notification(
        db=db,
        user_id=user_id,
        request=request,
        is_in_active_focus_session=is_in_active_focus_session,
        focus_remaining_minutes=focus_remaining_minutes,
    )


@router.get(
    "/notifications/preferences",
    response_model=NotificationPreferenceRead,
    summary="Get Notification Preferences",
    description="Retrieves active user quiet hours, rate limits, category toggles, and pause status.",
)
def get_notification_preferences(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    return NotificationService.get_or_create_preferences(db=db, user_id=user_id)


@router.post(
    "/notifications/preferences",
    response_model=NotificationPreferenceRead,
    summary="Update Notification Preferences",
    description="Updates user quiet hours, hourly and daily notification limits, category toggles, or pause durations.",
)
def update_notification_preferences(
    update_data: NotificationPreferenceUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    return NotificationService.update_preferences(db=db, user_id=user_id, update_data=update_data)


@router.post(
    "/notifications/{id}/acknowledge",
    response_model=NotificationAcknowledgeResponse,
    summary="Acknowledge Notification",
    description="Marks notification as read/acknowledged and registers user acceptance in the cognitive fatigue model.",
)
def acknowledge_notification(
    id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    notif = NotificationService.acknowledge_notification(db=db, user_id=user_id, notification_id=id)
    return NotificationAcknowledgeResponse(
        id=notif.id,
        is_read=notif.is_read,
        acknowledged_at=notif.read_at or notif.created_at,
        message="Notification acknowledged.",
    )


@router.post(
    "/notifications/{id}/dismiss",
    response_model=NotificationDismissResponse,
    summary="Dismiss Notification",
    description="Dismisses notification and updates interaction fatigue patterns and annoyance metrics.",
)
def dismiss_notification(
    id: uuid.UUID,
    request: Optional[NotificationDismissRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    reason = request.reason if request else None
    annoyance = request.annoyance_level if request else None
    notif, updated_score = NotificationService.dismiss_notification(
        db=db, user_id=user_id, notification_id=id, reason=reason, annoyance_level=annoyance
    )
    return NotificationDismissResponse(
        id=notif.id,
        is_dismissed=notif.is_dismissed,
        dismissed_at=notif.dismissed_at or notif.created_at,
        updated_fatigue_score=updated_score,
        message="Notification dismissed.",
    )


@router.get(
    "/notifications/metrics",
    response_model=NotificationMetricsResponse,
    summary="Get Cognitive Notification Metrics",
    description="Returns user interaction fatigue score, weekly presentation counts, acceptance rate, and channel distribution.",
)
def get_notification_metrics(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.services.adaptive.notification_service import NotificationService
    return NotificationService.get_metrics(db=db, user_id=user_id)





