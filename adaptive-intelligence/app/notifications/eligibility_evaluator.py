"""
Eligibility Evaluator for ContextIQ Notification Intelligence (Phase 4.8).
Mirror for adaptive-intelligence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas.notification_schemas import (
    DeliveryStrategy,
    NotificationCategory,
    NotificationPriority,
)


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_local_hour(dt: datetime, tz_str: str = "UTC") -> int:
    try:
        user_tz = ZoneInfo(tz_str)
    except (ZoneInfoNotFoundError, ValueError):
        user_tz = timezone.utc

    local_dt = dt.astimezone(user_tz)
    return local_dt.hour


class EligibilityEvaluator:
    CRITICAL_DEADLINE_THRESHOLD_HOURS: float = 2.0
    DEFAULT_DEDUPLICATION_WINDOW_MINUTES: int = 30

    @classmethod
    def is_in_quiet_hours(cls, start_hour: int, end_hour: int, current_hour: int) -> bool:
        if start_hour == end_hour:
            return False
        if start_hour > end_hour:
            return current_hour >= start_hour or current_hour < end_hour
        return start_hour <= current_hour < end_hour

    @classmethod
    def evaluate_eligibility(
        cls,
        category: str,
        priority: str,
        user_timezone: str = "UTC",
        as_of: Optional[datetime] = None,
        deadline_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_critical_urgency: bool = False,
        is_in_active_focus_session: bool = False,
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
        dedup_window_minutes: int = DEFAULT_DEDUPLICATION_WINDOW_MINUTES,
    ) -> Tuple[bool, DeliveryStrategy, Optional[str]]:
        now = _normalize_utc(as_of) or datetime.now(timezone.utc)

        if enabled_categories is not None and not enabled_categories.get(category, True):
            return False, DeliveryStrategy.NO_NOTIFICATION, f"Category '{category}' is disabled in user preferences."

        if expires_at is not None:
            exp_utc = _normalize_utc(expires_at)
            if now >= exp_utc:
                return False, DeliveryStrategy.EXPIRED, f"Notification expired at {exp_utc.isoformat()}."

        is_imminent_deadline = False
        if deadline_at is not None:
            dl_utc = _normalize_utc(deadline_at)
            hrs_remaining = (dl_utc - now).total_seconds() / 3600.0
            if hrs_remaining <= cls.CRITICAL_DEADLINE_THRESHOLD_HOURS:
                is_imminent_deadline = True

        is_emergency = is_critical_urgency or is_imminent_deadline or priority == NotificationPriority.CRITICAL.value

        if is_paused:
            if paused_until is None or now < _normalize_utc(paused_until):
                if not is_emergency:
                    return False, DeliveryStrategy.SUPPRESSED_QUIET_PERIOD, "User has paused all non-critical notifications."

        if recent_duplicate_timestamps:
            dedup_cutoff = now - timedelta(minutes=dedup_window_minutes)
            for dup_ts in recent_duplicate_timestamps:
                d_utc = _normalize_utc(dup_ts)
                if d_utc >= dedup_cutoff:
                    return False, DeliveryStrategy.SUPPRESSED_DUPLICATE, (
                        f"Duplicate notification delivered within the last {dedup_window_minutes} minutes."
                    )

        if is_in_active_focus_session and not is_emergency:
            return False, DeliveryStrategy.DEFERRED, (
                "Active focus session in progress; non-critical notifications are deferred to preserve flow."
            )

        if quiet_hours_enabled and not is_emergency:
            local_hour = _get_local_hour(now, user_timezone)
            if cls.is_in_quiet_hours(quiet_hours_start, quiet_hours_end, local_hour):
                return False, DeliveryStrategy.SUPPRESSED_QUIET_PERIOD, (
                    f"Current local time ({local_hour}:00 in {user_timezone}) falls within quiet hours "
                    f"({quiet_hours_start:02d}:00 - {quiet_hours_end:02d}:00)."
                )

        if not is_emergency:
            if recent_deliveries_past_hour >= max_per_hour:
                return False, DeliveryStrategy.DEFERRED, (
                    f"Hourly notification limit reached ({recent_deliveries_past_hour}/{max_per_hour}); deferred."
                )
            if recent_deliveries_today >= max_per_day:
                return False, DeliveryStrategy.BATCHED_SUMMARY, (
                    f"Daily notification limit reached ({recent_deliveries_today}/{max_per_day}); batched to summary."
                )

        return True, DeliveryStrategy.IMMEDIATE, "Passed all cognitive eligibility preconditions."
