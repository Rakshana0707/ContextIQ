"""
Service layer for ContextIQ Notification Intelligence and Cognitive Load Management (Phase 4.8).
Orchestrates:
- Notification evaluation and scheduling against cognitive shielding policies.
- User notification preferences, quiet hours, and pause toggles.
- Delivery lifecycle tracking (immediate, deferred, batched, suppressed, expired).
- Fatigue tracking and algorithmic cognitive load scoring.
- Tenant isolation across all notification entities.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification_models import (
    NotificationFatigueRecord,
    UserNotification,
    UserNotificationPreference,
)
from app.models.user import User
from app.notifications.delivery_policy import DeliveryPolicyResolver
from app.notifications.eligibility_evaluator import EligibilityEvaluator, _normalize_utc
from app.notifications.fatigue_tracker import NotificationFatigueTracker
from app.schemas.notification_schemas import (
    DeliveryChannel,
    DeliveryStrategy,
    NotificationCategory,
    NotificationCreateRequest,
    NotificationMetricsResponse,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationPriority,
)


class NotificationService:
    """Service handling cognitive notification dispatch, user controls, and fatigue modeling."""

    @classmethod
    def get_or_create_preferences(
        cls, db: Session, user_id: uuid.UUID
    ) -> UserNotificationPreference:
        """Retrieves or initializes user notification preferences."""
        pref = db.scalar(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        )
        if not pref:
            pref = UserNotificationPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                enabled_categories={
                    NotificationCategory.CRITICAL_DEADLINE_REMINDER.value: True,
                    NotificationCategory.HIGH_FORGETTING_RISK_ALERT.value: True,
                    NotificationCategory.RECOVERY_SUGGESTION.value: True,
                    NotificationCategory.FOCUS_SESSION_SUGGESTION.value: True,
                    NotificationCategory.CONTEXTUAL_REMINDER.value: True,
                    NotificationCategory.DAILY_BEHAVIORAL_SUMMARY.value: True,
                },
                quiet_hours_start=22,
                quiet_hours_end=8,
                quiet_hours_enabled=True,
                max_notifications_per_hour=3,
                max_notifications_per_day=12,
                summary_frequency="DAILY",
                is_paused=False,
                desktop_agent_enabled=True,
                sound_enabled=False,
            )
            db.add(pref)
            db.commit()
            db.refresh(pref)
        return pref

    @classmethod
    def update_preferences(
        cls, db: Session, user_id: uuid.UUID, update_data: NotificationPreferenceUpdate
    ) -> UserNotificationPreference:
        """Updates user notification preferences and optional pause schedule."""
        pref = cls.get_or_create_preferences(db, user_id)

        if update_data.enabled_categories is not None:
            # Merge with existing categories
            current = dict(pref.enabled_categories or {})
            current.update(update_data.enabled_categories)
            pref.enabled_categories = current

        if update_data.quiet_hours_start is not None:
            pref.quiet_hours_start = update_data.quiet_hours_start
        if update_data.quiet_hours_end is not None:
            pref.quiet_hours_end = update_data.quiet_hours_end
        if update_data.quiet_hours_enabled is not None:
            pref.quiet_hours_enabled = update_data.quiet_hours_enabled

        if update_data.max_notifications_per_hour is not None:
            pref.max_notifications_per_hour = update_data.max_notifications_per_hour
        if update_data.max_notifications_per_day is not None:
            pref.max_notifications_per_day = update_data.max_notifications_per_day

        if update_data.summary_frequency is not None:
            pref.summary_frequency = update_data.summary_frequency.value

        if update_data.is_paused is not None:
            pref.is_paused = update_data.is_paused
            if update_data.is_paused:
                mins = update_data.pause_duration_minutes or 60
                pref.paused_until = datetime.now(timezone.utc) + timedelta(minutes=mins)
            else:
                pref.paused_until = None

        if update_data.desktop_agent_enabled is not None:
            pref.desktop_agent_enabled = update_data.desktop_agent_enabled
        if update_data.sound_enabled is not None:
            pref.sound_enabled = update_data.sound_enabled

        pref.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(pref)
        return pref

    @classmethod
    def get_or_create_fatigue_record(
        cls, db: Session, user_id: uuid.UUID
    ) -> NotificationFatigueRecord:
        """Retrieves or initializes user interaction fatigue tracking record."""
        rec = db.scalar(
            select(NotificationFatigueRecord).where(NotificationFatigueRecord.user_id == user_id)
        )
        if not rec:
            rec = NotificationFatigueRecord(
                id=uuid.uuid4(),
                user_id=user_id,
                total_presented_7d=0,
                total_accepted_7d=0,
                total_dismissed_7d=0,
                total_deferred_7d=0,
                consecutive_dismissals=0,
                calculated_fatigue_score=0.0,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
        return rec

    @classmethod
    def schedule_notification(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: NotificationCreateRequest,
        as_of: Optional[datetime] = None,
        user_timezone: Optional[str] = None,
        is_in_active_focus_session: bool = False,
        focus_remaining_minutes: Optional[int] = None,
    ) -> UserNotification:
        """
        Evaluates cognitive eligibility and dispatches/schedules a candidate notification.
        """
        now = _normalize_utc(as_of) or datetime.now(timezone.utc)
        pref = cls.get_or_create_preferences(db, user_id)
        fatigue_rec = cls.get_or_create_fatigue_record(db, user_id)

        # Resolve user timezone from user model if not explicitly passed
        tz_str = user_timezone
        if not tz_str:
            user = db.get(User, user_id)
            tz_str = user.timezone if user and user.timezone else "UTC"

        # Count deliveries past hour and past 24 hours
        hour_cutoff = now - timedelta(hours=1)
        day_cutoff = now - timedelta(days=1)

        deliveries_hour = db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.is_delivered.is_(True),
                UserNotification.created_at >= hour_cutoff,
            )
        ) or 0

        deliveries_day = db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.is_delivered.is_(True),
                UserNotification.created_at >= day_cutoff,
            )
        ) or 0

        # Query recent duplicates for same category
        dup_cutoff = now - timedelta(minutes=30)
        recent_dups = list(
            db.scalars(
                select(UserNotification.created_at).where(
                    UserNotification.user_id == user_id,
                    UserNotification.category == request.category.value,
                    UserNotification.created_at >= dup_cutoff,
                )
            ).all()
        )

        strategy, channel, deferred_until, rationale = DeliveryPolicyResolver.resolve_delivery(
            category=request.category.value,
            priority=request.priority.value,
            fatigue_score=fatigue_rec.calculated_fatigue_score,
            user_timezone=tz_str,
            as_of=now,
            deadline_at=request.deadline_at,
            expires_at=request.expires_at,
            is_critical_urgency=request.is_critical_urgency,
            is_in_active_focus_session=is_in_active_focus_session,
            focus_session_remaining_minutes=focus_remaining_minutes,
            enabled_categories=pref.enabled_categories,
            quiet_hours_enabled=pref.quiet_hours_enabled,
            quiet_hours_start=pref.quiet_hours_start,
            quiet_hours_end=pref.quiet_hours_end,
            is_paused=pref.is_paused,
            paused_until=pref.paused_until,
            recent_deliveries_past_hour=deliveries_hour,
            recent_deliveries_today=deliveries_day,
            max_per_hour=pref.max_notifications_per_hour,
            max_per_day=pref.max_notifications_per_day,
            recent_duplicate_timestamps=recent_dups,
            desktop_agent_enabled=pref.desktop_agent_enabled,
            preferred_channel=request.preferred_channel,
        )

        is_delivered = strategy == DeliveryStrategy.IMMEDIATE
        payload = dict(request.metadata_payload or {})
        payload["delivery_rationale"] = rationale

        notification = UserNotification(
            id=uuid.uuid4(),
            user_id=user_id,
            intervention_id=request.intervention_id,
            category=request.category.value,
            priority=request.priority.value,
            title=request.title,
            message=request.message,
            delivery_channel=channel.value,
            delivery_strategy=strategy.value,
            is_delivered=is_delivered,
            delivered_at=now if is_delivered else None,
            is_read=False,
            is_dismissed=False,
            is_deferred=(strategy == DeliveryStrategy.DEFERRED),
            deferred_until=deferred_until,
            expires_at=request.expires_at,
            metadata_payload=payload,
            created_at=now,
        )

        db.add(notification)

        # Update fatigue record if presented
        if is_delivered:
            fatigue_rec.total_presented_7d += 1
            fatigue_rec.last_interaction_at = now
            fatigue_rec.calculated_fatigue_score = NotificationFatigueTracker.calculate_fatigue_score(
                total_presented=fatigue_rec.total_presented_7d,
                total_accepted=fatigue_rec.total_accepted_7d,
                total_dismissed=fatigue_rec.total_dismissed_7d,
                total_deferred=fatigue_rec.total_deferred_7d,
                consecutive_dismissals=fatigue_rec.consecutive_dismissals,
                deliveries_24h=deliveries_day + 1,
                daily_limit=pref.max_notifications_per_day,
            )

        db.commit()
        db.refresh(notification)
        return notification

    @classmethod
    def list_notifications(
        cls,
        db: Session,
        user_id: uuid.UUID,
        unread_only: bool = False,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[UserNotification]:
        """Lists user notifications with filtering and tenant isolation."""
        stmt = (
            select(UserNotification)
            .where(UserNotification.user_id == user_id)
            .order_by(UserNotification.created_at.desc())
        )

        if unread_only:
            stmt = stmt.where(UserNotification.is_read.is_(False), UserNotification.is_dismissed.is_(False))
        if category:
            stmt = stmt.where(UserNotification.category == category)

        stmt = stmt.limit(limit)
        return list(db.scalars(stmt).all())

    @classmethod
    def acknowledge_notification(
        cls, db: Session, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> UserNotification:
        """Marks notification as read/acknowledged and updates user acceptance stats."""
        notification = db.scalar(
            select(UserNotification).where(
                UserNotification.id == notification_id,
                UserNotification.user_id == user_id,
            )
        )
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification {notification_id} not found for this user.",
            )

        now = datetime.now(timezone.utc)
        notification.is_read = True
        notification.read_at = now

        # Update fatigue tracker: reset consecutive dismissals, increment accepted
        fatigue_rec = cls.get_or_create_fatigue_record(db, user_id)
        pref = cls.get_or_create_preferences(db, user_id)

        fatigue_rec.total_accepted_7d += 1
        fatigue_rec.consecutive_dismissals = 0
        fatigue_rec.last_interaction_at = now

        day_cutoff = now - timedelta(days=1)
        deliveries_day = db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.is_delivered.is_(True),
                UserNotification.created_at >= day_cutoff,
            )
        ) or 0

        fatigue_rec.calculated_fatigue_score = NotificationFatigueTracker.calculate_fatigue_score(
            total_presented=fatigue_rec.total_presented_7d,
            total_accepted=fatigue_rec.total_accepted_7d,
            total_dismissed=fatigue_rec.total_dismissed_7d,
            total_deferred=fatigue_rec.total_deferred_7d,
            consecutive_dismissals=0,
            deliveries_24h=deliveries_day,
            daily_limit=pref.max_notifications_per_day,
        )

        db.commit()
        db.refresh(notification)
        return notification

    @classmethod
    def dismiss_notification(
        cls,
        db: Session,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
        reason: Optional[str] = None,
        annoyance_level: Optional[int] = None,
    ) -> Tuple[UserNotification, float]:
        """Dismisses notification and updates interaction fatigue metrics."""
        notification = db.scalar(
            select(UserNotification).where(
                UserNotification.id == notification_id,
                UserNotification.user_id == user_id,
            )
        )
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification {notification_id} not found for this user.",
            )

        now = datetime.now(timezone.utc)
        notification.is_dismissed = True
        notification.dismissed_at = now
        if reason:
            payload = dict(notification.metadata_payload or {})
            payload["dismiss_reason"] = reason
            payload["annoyance_level"] = annoyance_level
            notification.metadata_payload = payload

        # Update fatigue record
        fatigue_rec = cls.get_or_create_fatigue_record(db, user_id)
        pref = cls.get_or_create_preferences(db, user_id)

        fatigue_rec.total_dismissed_7d += 1
        fatigue_rec.consecutive_dismissals += 1
        fatigue_rec.last_interaction_at = now

        day_cutoff = now - timedelta(days=1)
        deliveries_day = db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.is_delivered.is_(True),
                UserNotification.created_at >= day_cutoff,
            )
        ) or 0

        new_score = NotificationFatigueTracker.calculate_fatigue_score(
            total_presented=fatigue_rec.total_presented_7d,
            total_accepted=fatigue_rec.total_accepted_7d,
            total_dismissed=fatigue_rec.total_dismissed_7d,
            total_deferred=fatigue_rec.total_deferred_7d,
            consecutive_dismissals=fatigue_rec.consecutive_dismissals,
            deliveries_24h=deliveries_day,
            daily_limit=pref.max_notifications_per_day,
            annoyance_reports_count=1 if annoyance_level else 0,
            average_annoyance_level=float(annoyance_level) if annoyance_level else None,
        )
        fatigue_rec.calculated_fatigue_score = new_score

        db.commit()
        db.refresh(notification)
        return notification, new_score

    @classmethod
    def get_metrics(cls, db: Session, user_id: uuid.UUID) -> NotificationMetricsResponse:
        """Returns comprehensive cognitive load and notification distribution metrics."""
        pref = cls.get_or_create_preferences(db, user_id)
        fatigue_rec = cls.get_or_create_fatigue_record(db, user_id)
        now = datetime.now(timezone.utc)

        user = db.get(User, user_id)
        tz_str = user.timezone if user and user.timezone else "UTC"

        # Check if currently inside quiet hours
        local_hour = EligibilityEvaluator.is_in_quiet_hours(
            pref.quiet_hours_start,
            pref.quiet_hours_end,
            EligibilityEvaluator.is_in_quiet_hours(pref.quiet_hours_start, pref.quiet_hours_end, 12),
        )
        from app.notifications.eligibility_evaluator import _get_local_hour
        current_loc_hour = _get_local_hour(now, tz_str)
        is_quiet = pref.quiet_hours_enabled and EligibilityEvaluator.is_in_quiet_hours(
            pref.quiet_hours_start, pref.quiet_hours_end, current_loc_hour
        )

        # Count deliveries today and current hour
        day_cutoff = now - timedelta(days=1)
        hour_cutoff = now - timedelta(hours=1)

        deliveries_today = db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.is_delivered.is_(True),
                UserNotification.created_at >= day_cutoff,
            )
        ) or 0

        deliveries_hour = db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.is_delivered.is_(True),
                UserNotification.created_at >= hour_cutoff,
            )
        ) or 0

        # Distribution by channel and category (past 7 days)
        week_cutoff = now - timedelta(days=7)
        notifs_7d = list(
            db.scalars(
                select(UserNotification).where(
                    UserNotification.user_id == user_id,
                    UserNotification.created_at >= week_cutoff,
                )
            ).all()
        )

        chan_dist: Dict[str, int] = {}
        cat_dist: Dict[str, int] = {}
        for n in notifs_7d:
            chan_dist[n.delivery_channel] = chan_dist.get(n.delivery_channel, 0) + 1
            cat_dist[n.category] = cat_dist.get(n.category, 0) + 1

        acc_rate = (
            round(fatigue_rec.total_accepted_7d / max(1, fatigue_rec.total_presented_7d), 3)
            if fatigue_rec.total_presented_7d > 0
            else 0.0
        )

        fatigue_tier = NotificationFatigueTracker.get_fatigue_level(fatigue_rec.calculated_fatigue_score)

        return NotificationMetricsResponse(
            user_id=user_id,
            fatigue_score=fatigue_rec.calculated_fatigue_score,
            fatigue_level=fatigue_tier,
            total_presented_7d=fatigue_rec.total_presented_7d,
            total_accepted_7d=fatigue_rec.total_accepted_7d,
            total_dismissed_7d=fatigue_rec.total_dismissed_7d,
            total_deferred_7d=fatigue_rec.total_deferred_7d,
            acceptance_rate_7d=acc_rate,
            consecutive_dismissals=fatigue_rec.consecutive_dismissals,
            active_quiet_hours=is_quiet,
            is_paused=pref.is_paused,
            paused_until=pref.paused_until,
            notifications_delivered_today=deliveries_today,
            notifications_delivered_current_hour=deliveries_hour,
            channel_distribution=chan_dist,
            category_distribution=cat_dist,
        )
