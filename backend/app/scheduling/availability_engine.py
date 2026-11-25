"""Availability engine calculating realistic cognitive and task scheduling windows."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.focus_window import UserFocusWindow
from app.schemas.scheduling import (
    AvailabilityWindowRead,
    BusyBlockRead,
    UserAvailabilityResponse,
)

logger = logging.getLogger(__name__)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def subtract_interval(
    free_intervals: List[Tuple[datetime, datetime]],
    busy_start: datetime,
    busy_end: datetime,
) -> List[Tuple[datetime, datetime]]:
    """Subtracts a busy interval [busy_start, busy_end] from a collection of free intervals."""
    new_free: List[Tuple[datetime, datetime]] = []
    for f_start, f_end in free_intervals:
        if busy_end <= f_start or busy_start >= f_end:
            # No intersection
            new_free.append((f_start, f_end))
        else:
            # Overlap occurs: clip left and/or right pieces
            if f_start < busy_start:
                new_free.append((f_start, busy_start))
            if busy_end < f_end:
                new_free.append((busy_end, f_end))
    return new_free


class AvailabilityEngine:
    """Calculates realistic available working windows for task placement."""

    @classmethod
    def calculate_availability(
        cls,
        db: Session,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        horizon_days: int = 3,
        working_hour_start: int = 9,
        working_hour_end: int = 17,
        include_weekends: bool = False,
        enforce_lunch_break: bool = True,
        lunch_start_hour: int = 12,
        lunch_duration_minutes: int = 60,
        recovery_buffer_minutes: int = 15,
        min_slot_minutes: int = 15,
    ) -> UserAvailabilityResponse:
        """Computes free and busy time intervals across external calendars, working hours, and recovery buffers.

        Invariant: An empty calendar does NOT imply 24h availability; all slots are strictly
        clamped to human working hours and bounded by cognitive recovery breaks.
        """
        now_utc = datetime.now(timezone.utc)
        horizon_start = _to_utc(start_date) or now_utc

        # Align horizon_start to beginning of current day in UTC
        current_day_start = horizon_start.replace(hour=0, minute=0, second=0, microsecond=0)
        horizon_end = current_day_start + timedelta(days=horizon_days)

        busy_blocks: List[BusyBlockRead] = []
        raw_free_intervals: List[Tuple[datetime, datetime]] = []

        # 1. Query external calendar events across Google and Microsoft Outlook
        cal_stmt = (
            select(ExternalCalendarEvent)
            .where(
                ExternalCalendarEvent.user_id == user_id,
                ExternalCalendarEvent.status != "CANCELLED",
                ExternalCalendarEvent.transparency == "OPAQUE",  # Busy meetings block focus time
                ExternalCalendarEvent.start_time < horizon_end,
                ExternalCalendarEvent.end_time > horizon_start,
            )
            .order_by(ExternalCalendarEvent.start_time.asc())
        )
        calendar_events = list(db.scalars(cal_stmt).all())

        # 2. Iterate each day in the horizon and establish working hours boundaries
        for day_offset in range(horizon_days):
            day_cursor = current_day_start + timedelta(days=day_offset)

            # Check weekends (Saturday = 5, Sunday = 6)
            if not include_weekends and day_cursor.weekday() in (5, 6):
                continue

            work_start = day_cursor.replace(hour=working_hour_start, minute=0, second=0, microsecond=0)
            work_end = day_cursor.replace(hour=working_hour_end, minute=0, second=0, microsecond=0)

            # If horizon_start is today and current time is past work_start, clamp start time
            effective_start = max(work_start, horizon_start)
            if effective_start >= work_end:
                continue

            daily_free = [(effective_start, work_end)]

            # A. Enforce Lunch Break
            if enforce_lunch_break:
                lunch_start = day_cursor.replace(hour=lunch_start_hour, minute=0, second=0, microsecond=0)
                lunch_end = lunch_start + timedelta(minutes=lunch_duration_minutes)

                if lunch_start < work_end and lunch_end > effective_start:
                    clamped_lunch_start = max(lunch_start, effective_start)
                    clamped_lunch_end = min(lunch_end, work_end)
                    daily_free = subtract_interval(daily_free, clamped_lunch_start, clamped_lunch_end)
                    busy_blocks.append(
                        BusyBlockRead(
                            title="Lunch Break",
                            start_time=clamped_lunch_start,
                            end_time=clamped_lunch_end,
                            source="lunch_break",
                            is_recovery_buffer=False,
                        )
                    )

            # B. Apply Calendar Events and Post-Meeting Recovery Buffers
            for evt in calendar_events:
                e_start = _to_utc(evt.start_time)
                e_end = _to_utc(evt.end_time)

                if e_start < work_end and e_end > effective_start:
                    clamped_m_start = max(e_start, effective_start)
                    clamped_m_end = min(e_end, work_end)

                    # Subtract meeting busy block
                    daily_free = subtract_interval(daily_free, clamped_m_start, clamped_m_end)
                    busy_blocks.append(
                        BusyBlockRead(
                            title=evt.title,
                            start_time=clamped_m_start,
                            end_time=clamped_m_end,
                            source=getattr(evt, "provider", None) or "calendar",
                            is_recovery_buffer=False,
                        )
                    )

                    # Subtract Cognitive Recovery Buffer
                    if recovery_buffer_minutes > 0:
                        buf_start = clamped_m_end
                        buf_end = min(buf_start + timedelta(minutes=recovery_buffer_minutes), work_end)
                        if buf_end > buf_start:
                            daily_free = subtract_interval(daily_free, buf_start, buf_end)
                            busy_blocks.append(
                                BusyBlockRead(
                                    title=f"Post-Meeting Recovery Buffer ({recovery_buffer_minutes}m)",
                                    start_time=buf_start,
                                    end_time=buf_end,
                                    source="recovery_buffer",
                                    is_recovery_buffer=True,
                                )
                            )

            raw_free_intervals.extend(daily_free)

        # 3. Discover user's personal focus windows for quality scoring
        fw_stmt = select(UserFocusWindow).where(
            UserFocusWindow.user_id == user_id,
            UserFocusWindow.is_active.is_(True),
        )
        focus_windows = list(db.scalars(fw_stmt).all())

        available_windows: List[AvailabilityWindowRead] = []
        total_available_minutes = 0

        for f_start, f_end in raw_free_intervals:
            duration_mins = int((f_end - f_start).total_seconds() / 60.0)
            if duration_mins < min_slot_minutes:
                continue

            # Evaluate focus quality based on discovered personal windows or circadian baseline
            quality_score = 50.0
            is_peak = False

            # Check overlap with discovered focus windows
            for fw in focus_windows:
                fw_start_h = fw.start_time.hour if hasattr(fw.start_time, "hour") else 9
                fw_end_h = fw.end_time.hour if hasattr(fw.end_time, "hour") else 12
                # Check hour alignment
                if fw_start_h <= f_start.hour < fw_end_h:
                    quality_score = max(quality_score, fw.quality_score)
                    if fw.quality_score >= 60.0:
                        is_peak = True

            # If cold start, circadian baseline: mid-morning 09:30 - 11:30 is elevated focus quality
            if not focus_windows:
                if 9 <= f_start.hour <= 11:
                    quality_score = 75.0
                    is_peak = True
                elif 14 <= f_start.hour <= 16:
                    quality_score = 65.0

            available_windows.append(
                AvailabilityWindowRead(
                    start_time=f_start,
                    end_time=f_end,
                    duration_minutes=duration_mins,
                    focus_quality_score=round(quality_score, 1),
                    is_peak_focus=is_peak,
                )
            )
            total_available_minutes += duration_mins

        # Sort busy blocks and free windows chronologically
        busy_blocks.sort(key=lambda b: b.start_time)
        available_windows.sort(key=lambda w: w.start_time)

        return UserAvailabilityResponse(
            user_id=user_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            working_hours_start=f"{working_hour_start:02d}:00",
            working_hours_end=f"{working_hour_end:02d}:00",
            total_available_minutes=total_available_minutes,
            available_windows=available_windows,
            busy_blocks=busy_blocks,
        )
