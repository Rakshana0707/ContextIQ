"""
Intelligent Work Session Reconstruction Engine (ContextIQ Phase 3.6).

Upgrades ContextIQ's session reconstruction pipeline to process automatically
collected desktop telemetry alongside manual task events and behavioral interruptions.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel
from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.models.context_session import ContextSession
from app.models.detected_interruption import DetectedInterruption
from app.models.enums import DetectedInterruptionType, TaskEventType, TelemetryEventType
from app.models.interruption import Interruption
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.context_session import (
    ContextSessionCorrectionRequest,
    SessionTimelineSegment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class SessionReconstructionConfig(BaseModel):
    """Configurable boundaries and thresholds for session reconstruction."""
    session_idle_timeout_minutes: float = 30.0    # >= 30m idle ends the session
    pause_idle_threshold_minutes: float = 5.0     # >= 5m idle pauses the session
    min_session_duration_seconds: float = 60.0    # discard phantom sessions < 1m
    max_session_duration_hours: float = 8.0       # clamp runaway open sessions at 8h
    micro_glance_threshold_seconds: float = 3.0   # ignore switches < 3s in productive time
    lookback_window_hours: int = 24               # default incremental processing window


# ---------------------------------------------------------------------------
# Intermediate Internal Data Structures
# ---------------------------------------------------------------------------

@dataclass
class UnifiedEvent:
    event_id: str
    event_type: str  # APP_ACTIVATED, APP_DEACTIVATED, IDLE_START, IDLE_RETURN, TASK_EVENT, INTERRUPTION
    timestamp: datetime
    app_id: Optional[str] = None
    task_id: Optional[uuid.UUID] = None
    duration: float = 0.0
    device_id: Optional[str] = None
    device_type: str = "DESKTOP"
    payload: Dict[str, Any] = field(default_factory=dict)


def _normalize_app_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    cleaned = name.strip().lower()
    if "\\" in cleaned:
        cleaned = cleaned.split("\\")[-1]
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    return cleaned


# ---------------------------------------------------------------------------
# Session Reconstruction Engine Core
# ---------------------------------------------------------------------------

class SessionReconstructionEngine:
    """
    Synthesizes cohesive multi-application work sessions from telemetry events,
    task events, and interruptions.
    """

    def __init__(self, config: Optional[SessionReconstructionConfig] = None):
        self.config = config or SessionReconstructionConfig()

    def merge_and_sort_events(
        self,
        telemetry_events: Sequence[RawTelemetryEvent],
        task_events: Sequence[TaskEvent],
        detected_interruptions: Sequence[DetectedInterruption],
        manual_interruptions: Sequence[Interruption],
    ) -> List[UnifiedEvent]:
        """Merges multiple event streams into a single chronologically sorted sequence."""
        unified: List[UnifiedEvent] = []
        seen_ids: Set[str] = set()

        # 1. Telemetry Events
        for ev in telemetry_events:
            eid = str(ev.event_id)
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            ts = ev.event_timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            dev_type = (ev.payload or {}).get("device_type") if ev.payload else None
            if not dev_type:
                if "mobile" in (ev.source or "").lower() or (ev.device_id and "mobile" in str(ev.device_id).lower()):
                    dev_type = "MOBILE"
                else:
                    dev_type = "DESKTOP"

            unified.append(
                UnifiedEvent(
                    event_id=eid,
                    event_type=ev.event_type,
                    timestamp=ts,
                    app_id=_normalize_app_name(ev.application_identifier or ev.current_application_identifier),
                    device_id=ev.device_id,
                    device_type=dev_type,
                    payload=ev.payload or {},
                )
            )

        # 2. Task Events
        for tev in task_events:
            eid = f"task-ev-{tev.id}"
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            ts = getattr(tev, "occurred_at", getattr(tev, "event_time", None))
            if ts is None:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            unified.append(
                UnifiedEvent(
                    event_id=eid,
                    event_type=f"TASK_{tev.event_type.value}",
                    timestamp=ts,
                    task_id=tev.task_id,
                    device_type="WEB",
                    payload={"event_type": tev.event_type.value},
                )
            )

        # 3. Detected Interruptions (Phase 3.5)
        for di in detected_interruptions:
            eid = f"det-int-{di.id}"
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            ts = di.start_timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            unified.append(
                UnifiedEvent(
                    event_id=eid,
                    event_type="DETECTED_INTERRUPTION",
                    timestamp=ts,
                    app_id=_normalize_app_name(di.interrupting_app),
                    duration=di.duration_seconds or 0.0,
                    payload={
                        "interruption_id": str(di.id),
                        "interruption_type": di.interruption_type.value if hasattr(di.interruption_type, "value") else str(di.interruption_type),
                        "severity": di.severity.value if hasattr(di.severity, "value") else str(di.severity),
                        "explanation": di.explanation,
                        "resumption_lag": di.resumption_lag_seconds,
                    },
                )
            )

        # 4. Manual Interruptions
        for mi in manual_interruptions:
            eid = f"man-int-{mi.id}"
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            ts = mi.occurred_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            unified.append(
                UnifiedEvent(
                    event_id=eid,
                    event_type="MANUAL_INTERRUPTION",
                    timestamp=ts,
                    task_id=mi.task_id,
                    duration=float(mi.duration_seconds or 0),
                    payload={"notes": mi.notes, "type": str(mi.interruption_type)},
                )
            )

        # Chronological sort
        unified.sort(key=lambda x: x.timestamp)
        return unified

    def reconstruct(
        self,
        unified_events: List[UnifiedEvent],
        user_id: uuid.UUID,
        active_tasks: Optional[Dict[uuid.UUID, Task]] = None,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Segments the event stream into discrete, cohesive work sessions.
        Applies session boundary rules, task association, and quality scoring.
        """
        if not unified_events:
            return []

        now_dt = now or datetime.now(timezone.utc)
        idle_timeout_delta = timedelta(minutes=self.config.session_idle_timeout_minutes)
        pause_idle_delta = timedelta(minutes=self.config.pause_idle_threshold_minutes)

        sessions: List[Dict[str, Any]] = []

        # State tracking for the current open session
        current_session_events: List[UnifiedEvent] = []
        current_session_start: Optional[datetime] = None
        last_event_time: Optional[datetime] = None
        current_task_id: Optional[uuid.UUID] = None

        for ev in unified_events:
            # Check for task start / pause events that influence boundary
            is_task_start = ev.event_type in ("TASK_STARTED", "TASK_RESUMED", "TASK_CREATED")
            is_task_end = ev.event_type in ("TASK_COMPLETED", "TASK_CANCELLED", "TASK_FORGOTTEN")

            if current_session_start is None:
                # Open a new session
                current_session_start = ev.timestamp
                current_session_events = [ev]
                last_event_time = ev.timestamp
                if ev.task_id:
                    current_task_id = ev.task_id
                continue

            # Check gap since last event
            gap = (ev.timestamp - last_event_time).total_seconds() if last_event_time else 0.0

            # Session Boundary Condition: Inactivity gap >= session_idle_timeout_minutes
            # OR crossing midnight into a new day
            is_new_day = ev.timestamp.date() != last_event_time.date() if last_event_time else False
            is_idle_timeout = gap >= (self.config.session_idle_timeout_minutes * 60.0)

            if is_idle_timeout or is_new_day or is_task_end:
                # Finalize current session
                if is_task_end:
                    current_session_events.append(ev)
                    session_end = ev.timestamp
                else:
                    session_end = min(last_event_time + idle_timeout_delta, ev.timestamp)

                built_session = self._build_session(
                    events=current_session_events,
                    start_time=current_session_start,
                    end_time=session_end,
                    user_id=user_id,
                    explicit_task_id=current_task_id,
                    active_tasks=active_tasks,
                    closed_by_timeout=is_idle_timeout,
                )
                if built_session:
                    sessions.append(built_session)

                # Reset state
                current_session_start = ev.timestamp if not is_task_end else None
                current_session_events = [ev] if not is_task_end else []
                last_event_time = ev.timestamp if not is_task_end else None
                current_task_id = ev.task_id if (not is_task_end and ev.task_id) else None
            else:
                current_session_events.append(ev)
                last_event_time = ev.timestamp
                if ev.task_id:
                    current_task_id = ev.task_id

        # Close any dangling open session at end of stream
        if current_session_events and current_session_start:
            implied_end = min(
                last_event_time + idle_timeout_delta,
                now_dt,
            ) if last_event_time else current_session_start

            built_session = self._build_session(
                events=current_session_events,
                start_time=current_session_start,
                end_time=implied_end,
                user_id=user_id,
                explicit_task_id=current_task_id,
                active_tasks=active_tasks,
                closed_by_timeout=True,
            )
            if built_session:
                sessions.append(built_session)

        return sessions

    def _build_session(
        self,
        events: List[UnifiedEvent],
        start_time: datetime,
        end_time: datetime,
        user_id: uuid.UUID,
        explicit_task_id: Optional[uuid.UUID],
        active_tasks: Optional[Dict[uuid.UUID, Task]],
        closed_by_timeout: bool,
    ) -> Optional[Dict[str, Any]]:
        """Constructs a detailed ContextSession dict from clustered events."""
        duration_seconds = max(0.0, (end_time - start_time).total_seconds())
        if duration_seconds < self.config.min_session_duration_seconds:
            # Ignore phantom micro-sessions
            return None

        # Build application breakdown and timeline segments
        app_breakdown: Dict[str, float] = {}
        secondary_apps: Set[str] = set()
        timeline: List[Dict[str, Any]] = []

        focused_seconds = 0.0
        interruption_seconds = 0.0
        idle_seconds = 0.0
        transition_count = 0
        interruption_count = 0
        resume_delay_seconds: Optional[float] = None

        current_app: Optional[str] = None
        current_app_start: Optional[datetime] = None
        prior_pause_time: Optional[datetime] = None

        for idx, ev in enumerate(events):
            seg_start = ev.timestamp
            next_ts = events[idx + 1].timestamp if idx + 1 < len(events) else end_time
            seg_duration = max(0.0, (next_ts - seg_start).total_seconds())
            ev_type_norm = (ev.event_type or "").lower()

            if ev_type_norm in (TelemetryEventType.APPLICATION_ACTIVATED.value, "app_focus", "app_activated") and ev.app_id:
                if current_app and current_app != ev.app_id:
                    transition_count += 1
                current_app = ev.app_id
                app_breakdown[current_app] = app_breakdown.get(current_app, 0.0) + seg_duration

                timeline.append({
                    "segment_id": str(uuid.uuid4()),
                    "segment_type": "FOCUS",
                    "started_at": seg_start.isoformat(),
                    "ended_at": next_ts.isoformat(),
                    "duration_seconds": round(seg_duration, 2),
                    "application_identifier": current_app,
                    "task_id": str(explicit_task_id) if explicit_task_id else None,
                    "device_id": ev.device_id,
                    "device_type": ev.device_type,
                    "notes": f"Active in {current_app}",
                })
                focused_seconds += seg_duration

            elif ev_type_norm in (TelemetryEventType.USER_IDLE_STARTED.value, "idle_start", "idle_started"):
                idle_seconds += seg_duration
                prior_pause_time = seg_start
                timeline.append({
                    "segment_id": str(uuid.uuid4()),
                    "segment_type": "IDLE",
                    "started_at": seg_start.isoformat(),
                    "ended_at": next_ts.isoformat(),
                    "duration_seconds": round(seg_duration, 2),
                    "application_identifier": current_app,
                    "task_id": str(explicit_task_id) if explicit_task_id else None,
                    "device_id": ev.device_id,
                    "device_type": ev.device_type,
                    "notes": "User idle inactivity interval",
                })

            elif ev_type_norm in (TelemetryEventType.USER_ACTIVE_RETURNED.value, "idle_return", "active_returned"):
                if prior_pause_time:
                    resume_delay_seconds = max(0.0, (seg_start - prior_pause_time).total_seconds())
                timeline.append({
                    "segment_id": str(uuid.uuid4()),
                    "segment_type": "RESUME",
                    "started_at": seg_start.isoformat(),
                    "ended_at": next_ts.isoformat(),
                    "duration_seconds": round(seg_duration, 2),
                    "application_identifier": current_app,
                    "task_id": str(explicit_task_id) if explicit_task_id else None,
                    "device_id": ev.device_id,
                    "device_type": ev.device_type,
                    "notes": "Activity resumed",
                })

            elif ev.event_type in ("DETECTED_INTERRUPTION", "MANUAL_INTERRUPTION"):
                interruption_count += 1
                int_dur = ev.duration if ev.duration > 0 else seg_duration
                interruption_seconds += int_dur
                timeline.append({
                    "segment_id": str(uuid.uuid4()),
                    "segment_type": "INTERRUPTION",
                    "started_at": seg_start.isoformat(),
                    "ended_at": (seg_start + timedelta(seconds=int_dur)).isoformat(),
                    "duration_seconds": round(int_dur, 2),
                    "application_identifier": ev.app_id or current_app,
                    "task_id": str(explicit_task_id) if explicit_task_id else None,
                    "device_id": ev.device_id,
                    "device_type": ev.device_type,
                    "notes": ev.payload.get("explanation") or ev.payload.get("notes") or "Interruption event",
                })

            elif ev.event_type.startswith("TASK_"):
                if ev.event_type == "TASK_RESUMED" and prior_pause_time:
                    resume_delay_seconds = max(0.0, (seg_start - prior_pause_time).total_seconds())
                elif ev.event_type == "TASK_PAUSED":
                    prior_pause_time = seg_start

        # Determine Primary Application
        primary_app = None
        if app_breakdown:
            primary_app = max(app_breakdown.items(), key=lambda kv: kv[1])[0]
            secondary_apps = {k for k in app_breakdown.keys() if k != primary_app}

        # Context-switch frequency per hour
        hours = duration_seconds / 3600.0
        switch_freq = round(transition_count / hours, 2) if hours > 0 else 0.0

        # Adjust focused time: total duration - idle - interruptions (clamp at 0)
        net_focused = max(0.0, duration_seconds - idle_seconds - interruption_seconds)

        # Task Association Logic
        task_id = explicit_task_id
        task_assoc_status = "UNKNOWN"
        task_assoc_conf = None
        suggested_task_id = None

        if task_id:
            task_assoc_status = "EXPLICIT"
            task_assoc_conf = 0.95
        elif active_tasks:
            # Fallback suggestion if only one active task
            if len(active_tasks) == 1:
                suggested_task_id = next(iter(active_tasks.keys()))
                task_assoc_status = "SUGGESTED"
                task_assoc_conf = 0.70

        # Quality & Reconstruction Confidence Scoring
        confidence = 1.0
        quality_details: Dict[str, Any] = {
            "total_events": len(events),
            "closed_by_timeout": closed_by_timeout,
            "has_primary_app": primary_app is not None,
            "task_association_known": task_id is not None,
        }

        if closed_by_timeout:
            confidence -= 0.15
        if not task_id:
            confidence -= 0.05
        if not primary_app:
            confidence -= 0.10
        if len(events) < 3:
            confidence -= 0.10

        confidence = max(0.1, min(1.0, round(confidence, 2)))
        quality_tier = "HIGH" if confidence >= 0.85 else ("MEDIUM" if confidence >= 0.65 else "LOW")

        return {
            "user_id": user_id,
            "task_id": task_id,
            "started_at": start_time,
            "ended_at": end_time,
            "status": "COMPLETED",
            "task_count": 1 if task_id else 0,
            "interruption_count": interruption_count,
            "primary_application": primary_app,
            "secondary_applications": list(secondary_apps),
            "application_breakdown": {k: round(v, 2) for k, v in app_breakdown.items()},
            "transition_count": transition_count,
            "context_switch_frequency": switch_freq,
            "focused_time_seconds": round(net_focused, 2),
            "interruption_time_seconds": round(interruption_seconds, 2),
            "idle_time_seconds": round(idle_seconds, 2),
            "resume_delay_seconds": round(resume_delay_seconds, 2) if resume_delay_seconds else None,
            "task_association_status": task_assoc_status,
            "task_association_confidence": task_assoc_conf,
            "suggested_task_id": suggested_task_id,
            "reconstruction_confidence": confidence,
            "quality_tier": quality_tier,
            "quality_details": quality_details,
            "timeline": timeline,
            "user_corrected": False,
            "user_correction_notes": None,
            "last_reconstructed_at": datetime.now(timezone.utc),
        }


# ---------------------------------------------------------------------------
# Database Service Integration & Incremental Processing
# ---------------------------------------------------------------------------

def reconstruct_sessions_for_user(
    db: Session,
    user_id: uuid.UUID,
    lookback_hours: Optional[int] = 24,
    force_full_rebuild: bool = False,
    now: Optional[datetime] = None,
) -> int:
    """
    Executes incremental or full session reconstruction for a user.
    Preserves historical finalized sessions outside the lookback window.
    """
    now_dt = now or datetime.now(timezone.utc)
    engine = SessionReconstructionEngine()

    # Determine processing time window
    time_cutoff: Optional[datetime] = None
    if not force_full_rebuild and lookback_hours:
        time_cutoff = now_dt - timedelta(hours=lookback_hours)

    # 1. Fetch Telemetry Events
    telemetry_stmt = select(RawTelemetryEvent).where(RawTelemetryEvent.user_id == user_id)
    if time_cutoff:
        telemetry_stmt = telemetry_stmt.where(RawTelemetryEvent.event_timestamp >= time_cutoff)
    telemetry_events = list(db.scalars(telemetry_stmt).all())

    # 2. Fetch Task Events
    task_ev_stmt = select(TaskEvent).where(TaskEvent.user_id == user_id)
    if time_cutoff:
        task_time_col = getattr(TaskEvent, "occurred_at", getattr(TaskEvent, "event_time", None))
        if task_time_col is not None:
            task_ev_stmt = task_ev_stmt.where(task_time_col >= time_cutoff)
    task_events = list(db.scalars(task_ev_stmt).all())

    # 3. Fetch Detected Interruptions
    det_int_stmt = select(DetectedInterruption).where(DetectedInterruption.user_id == user_id)
    if time_cutoff:
        det_int_stmt = det_int_stmt.where(DetectedInterruption.start_timestamp >= time_cutoff)
    det_interruptions = list(db.scalars(det_int_stmt).all())

    # 4. Fetch Manual Interruptions
    man_int_stmt = select(Interruption).where(Interruption.user_id == user_id)
    if time_cutoff:
        man_int_stmt = man_int_stmt.where(Interruption.occurred_at >= time_cutoff)
    man_interruptions = list(db.scalars(man_int_stmt).all())

    # 5. Fetch Active Tasks
    active_tasks_list = db.scalars(select(Task).where(Task.user_id == user_id)).all()
    active_tasks_map = {t.id: t for t in active_tasks_list}

    # Merge and sort
    unified = engine.merge_and_sort_events(
        telemetry_events=telemetry_events,
        task_events=task_events,
        detected_interruptions=det_interruptions,
        manual_interruptions=man_interruptions,
    )

    if not unified:
        return 0

    reconstructed_candidates = engine.reconstruct(
        unified_events=unified,
        user_id=user_id,
        active_tasks=active_tasks_map,
        now=now_dt,
    )

    # Clean existing sessions only within the re-evaluation window
    if force_full_rebuild:
        db.execute(delete(ContextSession).where(ContextSession.user_id == user_id))
    elif time_cutoff:
        db.execute(
            delete(ContextSession).where(
                ContextSession.user_id == user_id,
                ContextSession.started_at >= time_cutoff,
                ContextSession.user_corrected.is_(False),  # Preserve manual user corrections
            )
        )

    created_count = 0
    for cand in reconstructed_candidates:
        session_obj = ContextSession(
            user_id=cand["user_id"],
            task_id=cand.get("task_id"),
            location_id=cand.get("location_id"),
            context_tag=cand.get("context_tag"),
            started_at=cand["started_at"],
            ended_at=cand.get("ended_at"),
            status=cand["status"],
            task_count=cand.get("task_count", 0),
            interruption_count=cand.get("interruption_count", 0),
            primary_application=cand.get("primary_application"),
            secondary_applications=cand.get("secondary_applications", []),
            application_breakdown=cand.get("application_breakdown", {}),
            transition_count=cand.get("transition_count", 0),
            context_switch_frequency=cand.get("context_switch_frequency", 0.0),
            focused_time_seconds=cand.get("focused_time_seconds", 0.0),
            interruption_time_seconds=cand.get("interruption_time_seconds", 0.0),
            idle_time_seconds=cand.get("idle_time_seconds", 0.0),
            resume_delay_seconds=cand.get("resume_delay_seconds"),
            task_association_status=cand.get("task_association_status", "UNKNOWN"),
            task_association_confidence=cand.get("task_association_confidence"),
            suggested_task_id=cand.get("suggested_task_id"),
            reconstruction_confidence=cand.get("reconstruction_confidence", 1.0),
            quality_tier=cand.get("quality_tier", "HIGH"),
            quality_details=cand.get("quality_details", {}),
            timeline=cand.get("timeline", []),
            user_corrected=cand.get("user_corrected", False),
            user_correction_notes=cand.get("user_correction_notes"),
            last_reconstructed_at=cand.get("last_reconstructed_at"),
        )
        db.add(session_obj)
        created_count += 1

    db.commit()
    return created_count


def get_context_session_by_id(
    db: Session, user_id: uuid.UUID, session_id: uuid.UUID
) -> Optional[ContextSession]:
    """Fetches a specific ContextSession verifying user ownership."""
    return db.execute(
        select(ContextSession).where(
            ContextSession.id == session_id,
            ContextSession.user_id == user_id,
        )
    ).scalar_one_or_none()


def query_context_sessions(
    db: Session,
    user_id: uuid.UUID,
    task_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    quality_tier: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[ContextSession], int]:
    """Retrieves paginated and filtered context sessions."""
    stmt = select(ContextSession).where(ContextSession.user_id == user_id)

    if task_id:
        stmt = stmt.where(ContextSession.task_id == task_id)
    if status:
        stmt = stmt.where(ContextSession.status == status)
    if quality_tier:
        stmt = stmt.where(ContextSession.quality_tier == quality_tier)
    if start_time:
        stmt = stmt.where(ContextSession.started_at >= start_time)
    if end_time:
        stmt = stmt.where(ContextSession.started_at <= end_time)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(desc(ContextSession.started_at)).limit(limit).offset(offset)
    items = list(db.scalars(stmt).all())
    return items, total


def correct_context_session(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: ContextSessionCorrectionRequest,
) -> ContextSession:
    """Applies user manual correction to a reconstructed session."""
    session_obj = get_context_session_by_id(db, user_id, session_id)
    if not session_obj:
        raise ValueError(f"Context session {session_id} not found.")

    if payload.task_id:
        # Verify task exists and belongs to user
        task = db.get(Task, payload.task_id)
        if not task or task.user_id != user_id:
            raise ValueError(f"Task {payload.task_id} does not exist or belong to user.")
        session_obj.task_id = payload.task_id
        session_obj.task_association_status = "USER_CORRECTED"
        session_obj.task_association_confidence = 1.0
        session_obj.task_count = 1

    session_obj.user_corrected = True
    session_obj.user_correction_notes = payload.notes
    session_obj.reconstruction_confidence = min(1.0, session_obj.reconstruction_confidence + 0.1)
    session_obj.quality_tier = "HIGH" if session_obj.reconstruction_confidence >= 0.85 else "MEDIUM"

    db.commit()
    db.refresh(session_obj)
    return session_obj
