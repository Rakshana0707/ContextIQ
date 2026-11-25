"""
Proactive Intelligence Service and Notification Fatigue Management (ContextIQ Phase 7.3).
Provides cognitive fatigue controls, quiet hours enforcement, conformal uncertainty
disclaimers, and structured recommendation feed creation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.event_models import ProactiveFeedItem
from app.models.notification_models import UserNotificationPreference
from app.schemas.event_schemas import StandardEvent, StandardEventType


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ProactiveIntelligenceService:
    """
    Evaluates behavioral events against fatigue constraints and publishes
    calibrated, actionable insights to the user's Proactive Feed.
    """

    MAX_PROACTIVE_DAILY_LIMIT: int = 3
    DUPLICATE_COOLDOWN_HOURS: int = 4

    @classmethod
    def evaluate_fatigue_and_eligibility(
        cls,
        db: Session,
        user_id: uuid.UUID,
        detection_type: str,
        now: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a proactive intelligence insight is eligible for delivery
        or should be suppressed due to quiet hours, duplicate cooldown, or daily fatigue limits.
        """
        current_time = _ensure_utc(now) or datetime.now(timezone.utc)

        # 1. Fetch user notification preferences
        pref = db.execute(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        ).scalar_one_or_none()

        if pref:
            # Check pause status
            if pref.is_paused:
                paused_until = _ensure_utc(pref.paused_until)
                if paused_until is None or paused_until > current_time:
                    return False, "User notifications are currently paused."

            # Check quiet hours
            if pref.quiet_hours_enabled:
                user_hour = current_time.hour
                start = pref.quiet_hours_start
                end = pref.quiet_hours_end
                is_quiet = False
                if start > end:  # Overnight: e.g. 22:00 to 08:00
                    if user_hour >= start or user_hour < end:
                        is_quiet = True
                else:  # Daytime quiet window
                    if start <= user_hour < end:
                        is_quiet = True

                if is_quiet:
                    return False, f"Quiet hours active ({start:02d}:00 - {end:02d}:00)."

        # 2. Daily fatigue volume ceiling (max 3 proactive recommendations per day)
        day_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = db.execute(
            select(func.count(ProactiveFeedItem.id)).where(
                and_(
                    ProactiveFeedItem.user_id == user_id,
                    ProactiveFeedItem.created_at >= day_start,
                )
            )
        ).scalar() or 0

        if daily_count >= cls.MAX_PROACTIVE_DAILY_LIMIT:
            return False, f"Daily proactive intelligence limit reached ({daily_count}/{cls.MAX_PROACTIVE_DAILY_LIMIT} today)."

        # 3. Duplicate suppression window (4-hour cooldown per detection type)
        duplicate_cutoff = current_time - timedelta(hours=cls.DUPLICATE_COOLDOWN_HOURS)
        recent_duplicate = db.execute(
            select(ProactiveFeedItem).where(
                and_(
                    ProactiveFeedItem.user_id == user_id,
                    ProactiveFeedItem.detection_type == detection_type,
                    ProactiveFeedItem.created_at >= duplicate_cutoff,
                )
            )
        ).first()

        if recent_duplicate:
            return False, f"Duplicate '{detection_type}' suppressed within {cls.DUPLICATE_COOLDOWN_HOURS}h cooldown."

        return True, None

    @classmethod
    def generate_feed_item_from_event(
        cls,
        db: Session,
        event: StandardEvent,
        now: Optional[datetime] = None,
        force: bool = False,
    ) -> Tuple[Optional[ProactiveFeedItem], Optional[str]]:
        """
        Creates a calibrated proactive feed item from a detected behavioral event,
        subject to fatigue management checks unless forced.
        """
        current_time = _ensure_utc(now) or datetime.now(timezone.utc)
        detection_type = event.event_type

        # Fatigue check
        if not force:
            eligible, reason = cls.evaluate_fatigue_and_eligibility(
                db=db,
                user_id=event.user_id,
                detection_type=detection_type,
                now=current_time,
            )
            if not eligible:
                return None, reason

        # Map event type to structured proactive feed attributes
        payload = event.payload or {}
        confidence = float(payload.get("confidence_score", 0.85))
        lower_bound = float(payload.get("uncertainty_lower_bound", max(0.60, confidence - 0.15)))
        upper_bound = float(payload.get("uncertainty_upper_bound", min(0.99, confidence + 0.08)))
        conformal_text = str(payload.get(
            "conformal_interval_text",
            f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (90% coverage)"
        ))

        title = "Behavioral Intelligence Insight"
        why_it_matters = "A significant pattern in task execution or attention was detected."
        recommended_response = "Review context and take action."
        suggested_action: Optional[Dict[str, Any]] = None
        related_task_id: Optional[uuid.UUID] = None

        if "task_id" in payload:
            try:
                related_task_id = uuid.UUID(str(payload["task_id"]))
            except (ValueError, TypeError):
                related_task_id = None

        if detection_type == StandardEventType.THRASHING_DETECTED.value:
            switches = payload.get("switch_count", 6)
            title = "Context Thrashing Detected"
            why_it_matters = (
                f"You switched applications {switches} times in the last minute. "
                "Rapid task switching degrades working memory and compounds cognitive fatigue."
            )
            recommended_response = "Shield your workspace with a 25-minute focus session or close unused tabs."
            suggested_action = {
                "action_type": "CREATE_FOCUS_SESSION",
                "label": "Start 25m Protected Focus",
                "parameters": {"duration_minutes": 25},
            }

        elif detection_type == StandardEventType.FORGETTING_RISK_SPIKE.value:
            task_title = payload.get("task_title", "Unfinished Task")
            prob = int(float(payload.get("lapse_probability", 0.75)) * 100)
            title = f"Forgetting Risk Spike: '{task_title}'"
            why_it_matters = (
                f"Statistical lapse probability reached {prob}%. "
                "Without a prompt, delayed micro-tasks have an exponentially lower resumption rate."
            )
            recommended_response = "Prepare a context reminder or re-anchor your current objective."
            suggested_action = {
                "action_type": "SEND_REMINDER",
                "label": "Send Task Reminder",
                "parameters": {"task_id": str(related_task_id) if related_task_id else None},
            }

        elif detection_type == StandardEventType.RECOVERY_LAG_EXCEEDED.value:
            lag = payload.get("excess_lag_minutes", 10.0)
            title = "Prolonged Post-Interruption Recovery"
            why_it_matters = (
                f"Resuming deep work took {lag} minutes longer than baseline. "
                "Consecutive delayed resumptions indicate cognitive depletion."
            )
            recommended_response = "Take a 5-minute cognitive reset buffer before beginning the next task."
            suggested_action = {
                "action_type": "SCHEDULE_RECOVERY_BUFFER",
                "label": "Inject 5m Recovery Break",
                "parameters": {"duration_minutes": 5},
            }

        elif detection_type == StandardEventType.CALENDAR_OVERLOAD.value:
            meetings = payload.get("consecutive_events_count", 3)
            title = "Dense Back-to-Back Schedule Overload"
            why_it_matters = (
                f"You have {meetings} consecutive meetings without transition intervals. "
                "Lack of buffer between meetings impairs executive function and increases error rates."
            )
            recommended_response = "Insert a 10-minute protective recovery buffer after this meeting cluster."
            suggested_action = {
                "action_type": "SCHEDULE_RECOVERY_BUFFER",
                "label": "Protect 10m Calendar Buffer",
                "parameters": {"duration_minutes": 10},
            }

        elif detection_type == StandardEventType.MISSED_RESUMPTION.value:
            task_title = payload.get("task_title", "Interrupted Task")
            minutes = payload.get("inactive_minutes", 45.0)
            title = f"Missed Task Resumption: '{task_title}'"
            why_it_matters = f"Work has been paused for {int(minutes)} minutes without re-engagement."
            recommended_response = "Resume now with saved context brief or mark task deferred."
            suggested_action = {
                "action_type": "RESUME_TASK",
                "label": "Resume Task",
                "parameters": {"task_id": str(related_task_id) if related_task_id else None},
            }

        elif detection_type == StandardEventType.BFI_SPIKE.value:
            delta = payload.get("delta", 0.25)
            title = "Behavioral Friction Spike Detected"
            why_it_matters = f"Micro-delay telemetry shows a +{delta:.2f} spike in friction against baseline."
            recommended_response = "Pause brief micro-tasks to restore attentional focus."
            suggested_action = {
                "action_type": "SUGGEST_BREAK",
                "label": "Schedule 10m Pause",
                "parameters": {"duration_minutes": 10},
            }

        feed_item = ProactiveFeedItem(
            user_id=event.user_id,
            event_id=event.event_id,
            detection_type=detection_type,
            title=title,
            why_it_matters=why_it_matters,
            related_task_id=related_task_id,
            related_context={"source": event.source, **payload},
            recommended_response=recommended_response,
            evidence={
                "event_type": event.event_type,
                "timestamp": event.event_timestamp.isoformat(),
                "payload": payload,
            },
            confidence_score=confidence,
            uncertainty_lower_bound=lower_bound,
            uncertainty_upper_bound=upper_bound,
            conformal_interval_text=conformal_text,
            status="ACTIVE",
            requires_approval=True,
            suggested_action=suggested_action,
            expires_at=current_time + timedelta(hours=24),
            created_at=current_time,
            updated_at=current_time,
        )

        db.add(feed_item)
        db.flush()
        return feed_item, None

    @classmethod
    def get_user_feed(
        cls,
        db: Session,
        user_id: uuid.UUID,
        status: Optional[str] = "ACTIVE",
        limit: int = 20,
    ) -> List[ProactiveFeedItem]:
        """Returns feed items for user, sorted by most recent."""
        query = select(ProactiveFeedItem).where(ProactiveFeedItem.user_id == user_id)
        if status:
            query = query.where(ProactiveFeedItem.status == status)
        query = query.order_by(ProactiveFeedItem.created_at.desc()).limit(limit)
        return list(db.execute(query).scalars().all())

    @classmethod
    def respond_to_feed_item(
        cls,
        db: Session,
        feed_item_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,  # 'APPROVE', 'SNOOZE', 'DISMISS'
        snooze_minutes: int = 60,
    ) -> Optional[ProactiveFeedItem]:
        """Handles user feedback on proactive feed recommendation."""
        item = db.execute(
            select(ProactiveFeedItem).where(
                and_(
                    ProactiveFeedItem.id == feed_item_id,
                    ProactiveFeedItem.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if not item:
            return None

        now = datetime.now(timezone.utc)
        action_upper = action.upper()
        if action_upper == "APPROVE":
            item.status = "ACTIONED"
        elif action_upper == "SNOOZE":
            item.status = "SNOOZED"
            item.snoozed_until = now + timedelta(minutes=snooze_minutes)
        elif action_upper == "DISMISS":
            item.status = "DISMISSED"

        item.updated_at = now
        db.commit()
        db.refresh(item)
        return item
