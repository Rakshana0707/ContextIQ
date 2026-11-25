"""
Delivery Policy Resolver for ContextIQ Notification Intelligence (Phase 4.8).
Mirror for adaptive-intelligence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.notifications.eligibility_evaluator import EligibilityEvaluator, _normalize_utc
from app.notifications.fatigue_tracker import NotificationFatigueTracker
from app.schemas.notification_schemas import (
    DeliveryChannel,
    DeliveryStrategy,
    NotificationCategory,
    NotificationPriority,
)


class DeliveryPolicyResolver:
    @classmethod
    def resolve_delivery(
        cls,
        category: str,
        priority: str,
        fatigue_score: float,
        user_timezone: str = "UTC",
        as_of: Optional[datetime] = None,
        deadline_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_critical_urgency: bool = False,
        is_in_active_focus_session: bool = False,
        focus_session_remaining_minutes: Optional[int] = None,
        enabled_categories: Optional[Dict[str, bool]] = None,
        quiet_hours_enabled: bool = True,
        quiet_hours_start: int = 22,
        quiet_hours_end: int = 8,
        is_paused: bool = False,
        paused_until: Optional[datetime] = None,
        recent_deliveries_past_hour: int = 0,
        recent_deliveries_today: int = 0,
        max_per_hour: int = 3,
        max_per_day: int = 12,
        recent_duplicate_timestamps: Optional[List[datetime]] = None,
        desktop_agent_enabled: bool = True,
        preferred_channel: Optional[DeliveryChannel] = None,
    ) -> Tuple[DeliveryStrategy, DeliveryChannel, Optional[datetime], str]:
        now = _normalize_utc(as_of) or datetime.now(timezone.utc)

        is_eligible, base_strategy, reason = EligibilityEvaluator.evaluate_eligibility(
            category=category,
            priority=priority,
            user_timezone=user_timezone,
            as_of=now,
            deadline_at=deadline_at,
            expires_at=expires_at,
            is_critical_urgency=is_critical_urgency,
            is_in_active_focus_session=is_in_active_focus_session,
            enabled_categories=enabled_categories,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            is_paused=is_paused,
            paused_until=paused_until,
            recent_deliveries_past_hour=recent_deliveries_past_hour,
            recent_deliveries_today=recent_deliveries_today,
            max_per_hour=max_per_hour,
            max_per_day=max_per_day,
            recent_duplicate_timestamps=recent_duplicate_timestamps,
        )

        if is_eligible and NotificationFatigueTracker.should_force_batch_summary(fatigue_score, priority):
            base_strategy = DeliveryStrategy.BATCHED_SUMMARY
            reason = (
                f"User notification fatigue score is high ({fatigue_score:.2f}); "
                f"rerouted to daily summary digest to reduce cognitive load."
            )

        channel = DeliveryChannel.IN_APP_NOTIFICATION_CENTER
        if preferred_channel:
            channel = preferred_channel
        elif priority == NotificationPriority.CRITICAL.value:
            if desktop_agent_enabled:
                channel = DeliveryChannel.DESKTOP_AGENT_NOTIFICATION
            else:
                channel = DeliveryChannel.WEB_IN_APP_TOAST
        elif priority == NotificationPriority.HIGH.value:
            channel = DeliveryChannel.WEB_IN_APP_TOAST
        else:
            channel = DeliveryChannel.IN_APP_NOTIFICATION_CENTER

        deferred_until = None
        if base_strategy == DeliveryStrategy.DEFERRED:
            delay_mins = focus_session_remaining_minutes if focus_session_remaining_minutes else 30
            deferred_until = now + timedelta(minutes=delay_mins)

        return base_strategy, channel, deferred_until, reason or "Delivery policy resolved."
