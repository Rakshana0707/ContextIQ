"""
Automated Interruption Detection and Classification Engine (ContextIQ Phase 3.5).

Transforms validated raw behavioral telemetry events into classified interruption
events, distinguishing normal workflow transitions from genuine behavioral disruptions.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.detected_interruption import (
    DetectedInterruption,
    DetectedInterruptionFeedback,
)
from app.models.enums import (
    DetectedInterruptionType,
    InterruptionFeedbackClassification,
    InterruptionSeverity,
    TelemetryEventType,
)
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.schemas.interruption import (
    DetectedInterruptionFeedbackCreate,
    InterruptionDetectionMetricsResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class InterruptionDetectionConfig(BaseModel):
    """Configurable thresholds and application definitions for detection rules."""

    # Inactivity thresholds (seconds)
    idle_threshold_seconds: float = 180.0       # < 3m is considered thinking/reading, >= 3m is idle disruption
    long_idle_threshold_seconds: float = 900.0  # >= 15m is high severity idle disruption
    critical_idle_threshold_seconds: float = 1800.0 # >= 30m is critical disruption

    # Switch dwell thresholds (seconds)
    micro_switch_threshold_seconds: float = 3.0  # < 3.0s is transient glance / alt-tab pass-through
    min_distraction_dwell_seconds: float = 15.0  # >= 15s in distracting app constitutes interruption
    max_resumption_lag_window_seconds: float = 60.0 # window to assess resumption delay

    # Rapid switching (thrashing) rules
    thrashing_window_seconds: float = 20.0
    thrashing_min_switches: int = 4
    thrashing_min_unique_apps: int = 2

    # Minimum dwell on primary app before it is established as active task context
    primary_task_min_dwell_seconds: float = 45.0

    # Complementary co-working application pairs that represent normal workflows
    # Normalized as lowercase basenames
    complementary_pairs: Set[Tuple[str, str]] = {
        ("code.exe", "cmd.exe"),
        ("code.exe", "powershell.exe"),
        ("code.exe", "windowsterminal.exe"),
        ("code.exe", "wt.exe"),
        ("code.exe", "git.exe"),
        ("code.exe", "bash.exe"),
        ("code.exe", "chrome.exe"),
        ("code.exe", "msedge.exe"),
        ("code.exe", "firefox.exe"),
        ("pycharm64.exe", "cmd.exe"),
        ("pycharm64.exe", "powershell.exe"),
        ("pycharm64.exe", "chrome.exe"),
        ("idea64.exe", "cmd.exe"),
        ("idea64.exe", "chrome.exe"),
        ("figma.exe", "chrome.exe"),
        ("figma.exe", "msedge.exe"),
    }

    # Known high-distraction external communication / entertainment apps
    distraction_apps: Set[str] = {
        "slack.exe",
        "teams.exe",
        "discord.exe",
        "whatsapp.exe",
        "telegram.exe",
        "spotify.exe",
        "outlook.exe",
        "thunderbird.exe",
        "netflix.exe",
        "steam.exe",
    }


# ---------------------------------------------------------------------------
# Normalized Telemetry Event Data Structure
# ---------------------------------------------------------------------------

@dataclass
class NormalizedEvent:
    event_id: str
    user_id: uuid.UUID
    device_id: Optional[str]
    event_type: str
    timestamp: datetime
    app_id: Optional[str]
    payload: Dict[str, Any]


def _normalize_app_name(app_name: Optional[str]) -> Optional[str]:
    if not app_name:
        return None
    cleaned = app_name.strip().lower()
    # Normalize backslashes and extract base file name if full path provided
    if "\\" in cleaned:
        cleaned = cleaned.split("\\")[-1]
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    return cleaned


# ---------------------------------------------------------------------------
# Interruption Detection Engine Core
# ---------------------------------------------------------------------------

class InterruptionDetector:
    """
    Detects and classifies behavioral interruptions from normalized event sequences.
    Applies false-positive suppression rules for intentional switching and micro-glances.
    """

    def __init__(self, config: Optional[InterruptionDetectionConfig] = None):
        self.config = config or InterruptionDetectionConfig()

    def is_complementary_pair(self, app_a: Optional[str], app_b: Optional[str]) -> bool:
        if not app_a or not app_b or app_a == app_b:
            return False
        pair = (app_a, app_b)
        reverse_pair = (app_b, app_a)
        return pair in self.config.complementary_pairs or reverse_pair in self.config.complementary_pairs

    def preprocess_events(self, raw_events: Sequence[Any]) -> List[NormalizedEvent]:
        """Deduplicates, parses, and chronologically sorts telemetry events."""
        normalized: List[NormalizedEvent] = []
        seen_ids: Set[str] = set()

        for item in raw_events:
            if isinstance(item, RawTelemetryEvent):
                eid = str(item.event_id)
                uid = item.user_id
                did = item.device_id
                etype = item.event_type
                ts = item.event_timestamp
                app = item.application_identifier or item.current_application_identifier
                payload = item.payload or {}
            elif isinstance(item, dict):
                eid = str(item.get("event_id") or uuid.uuid4())
                uid = uuid.UUID(str(item["user_id"])) if isinstance(item.get("user_id"), (str, uuid.UUID)) else uuid.uuid4()
                did = item.get("device_id")
                etype = str(item.get("event_type", ""))
                raw_ts = item.get("event_timestamp")
                if isinstance(raw_ts, datetime):
                    ts = raw_ts
                elif isinstance(raw_ts, str):
                    ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                else:
                    ts = datetime.now(timezone.utc)
                app = item.get("application_identifier") or item.get("current_application_identifier")
                payload = item.get("payload") or {}
            else:
                continue

            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            normalized.append(
                NormalizedEvent(
                    event_id=eid,
                    user_id=uid,
                    device_id=did,
                    event_type=etype,
                    timestamp=ts,
                    app_id=_normalize_app_name(app),
                    payload=payload,
                )
            )

        # Sort chronologically
        normalized.sort(key=lambda e: e.timestamp)
        return normalized

    def detect_interruptions(
        self, raw_events: Sequence[Any], user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        Main pipeline: Evaluates rule hierarchy over chronological event sequence.
        Returns candidate DetectedInterruption dictionaries ready for storage.
        """
        events = self.preprocess_events(raw_events)
        if not events:
            return []

        detected: List[Dict[str, Any]] = []

        # 1. Detect Idle Interruptions (inactivity periods)
        idle_interruptions = self._detect_idle_interruptions(events, user_id)
        detected.extend(idle_interruptions)

        # 2. Detect System Disruptions (lock / screensaver / agent pause)
        disruptions = self._detect_system_disruptions(events, user_id)
        detected.extend(disruptions)

        # 3. Detect Rapid Thrashing (pinballing context switches)
        thrashing_interruptions, thrash_event_ids = self._detect_thrashing(events, user_id)
        detected.extend(thrashing_interruptions)

        # 4. Detect Application Switch Interruptions (distraction diversions away from primary work)
        app_switch_interruptions = self._detect_app_switches(events, user_id, excluded_event_ids=thrash_event_ids)
        detected.extend(app_switch_interruptions)

        # Sort all detected interruptions chronologically by start_timestamp
        detected.sort(key=lambda x: x["start_timestamp"])
        return detected

    def _detect_idle_interruptions(
        self, events: List[NormalizedEvent], user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """Identifies sustained idle periods exceeding the idle threshold."""
        results: List[Dict[str, Any]] = []

        # Track active work application before idle
        last_work_app: Optional[str] = None
        for i, ev in enumerate(events):
            if ev.event_type == TelemetryEventType.APPLICATION_ACTIVATED.value and ev.app_id:
                last_work_app = ev.app_id

            if ev.event_type == TelemetryEventType.USER_IDLE_STARTED.value:
                idle_start = ev.timestamp
                idle_end: Optional[datetime] = None
                source_ids = [ev.event_id]

                # Find matching user_active_returned
                resumed_app = None
                for next_ev in events[i + 1 :]:
                    if next_ev.event_type == TelemetryEventType.USER_ACTIVE_RETURNED.value:
                        idle_end = next_ev.timestamp
                        source_ids.append(next_ev.event_id)
                        resumed_app = next_ev.app_id or last_work_app
                        break
                    elif next_ev.event_type == TelemetryEventType.APPLICATION_ACTIVATED.value:
                        # User returned and activated an app
                        idle_end = next_ev.timestamp
                        source_ids.append(next_ev.event_id)
                        resumed_app = next_ev.app_id
                        break

                if idle_end is not None:
                    duration = max(0.0, (idle_end - idle_start).total_seconds())
                else:
                    # Ongoing or unended idle from payload or default to 0
                    duration = float(ev.payload.get("duration_seconds", 0.0))
                    if duration > 0:
                        idle_end = idle_start + timedelta(seconds=duration)

                # Suppression Rule: micro-inactivity (< 180s) is considered normal reflection / reading
                if duration >= self.config.idle_threshold_seconds:
                    severity = self._classify_idle_severity(duration)
                    duration_min = round(duration / 60.0, 1)

                    app_context = f" while working in {last_work_app}" if last_work_app else ""
                    explanation = (
                        f"An interruption was detected because the user was inactive for {duration_min} minutes"
                        f"{app_context} before activity resumed."
                    )

                    results.append({
                        "user_id": user_id,
                        "source_event_ids": source_ids,
                        "interruption_type": DetectedInterruptionType.IDLE_INTERRUPTION,
                        "severity": severity,
                        "start_timestamp": idle_start,
                        "end_timestamp": idle_end,
                        "duration_seconds": round(duration, 2),
                        "confidence": 0.95,
                        "detection_method": "RULE_BASED_HEURISTIC",
                        "detection_version": "1.0.0",
                        "explanation": explanation,
                        "primary_app": last_work_app,
                        "interrupting_app": "system_idle",
                        "resumption_lag_seconds": None,
                        "metadata_payload": {
                            "idle_duration_seconds": duration,
                            "resumed_app": resumed_app,
                        },
                    })

        return results

    def _detect_system_disruptions(
        self, events: List[NormalizedEvent], user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """Identifies explicit system-level pauses, locks, or abrupt disruptions."""
        results: List[Dict[str, Any]] = []

        for i, ev in enumerate(events):
            if ev.event_type in (
                TelemetryEventType.TELEMETRY_PAUSED.value,
                TelemetryEventType.AGENT_STOPPED.value,
            ):
                start_ts = ev.timestamp
                end_ts: Optional[datetime] = None
                source_ids = [ev.event_id]

                for next_ev in events[i + 1 :]:
                    if next_ev.event_type in (
                        TelemetryEventType.TELEMETRY_RESUMED.value,
                        TelemetryEventType.AGENT_STARTED.value,
                    ):
                        end_ts = next_ev.timestamp
                        source_ids.append(next_ev.event_id)
                        break

                duration = (end_ts - start_ts).total_seconds() if end_ts else 0.0
                reason = ev.payload.get("reason", "system_pause")

                if duration >= self.config.idle_threshold_seconds:
                    severity = InterruptionSeverity.HIGH if duration >= self.config.long_idle_threshold_seconds else InterruptionSeverity.MEDIUM
                    results.append({
                        "user_id": user_id,
                        "source_event_ids": source_ids,
                        "interruption_type": DetectedInterruptionType.SESSION_DISRUPTION,
                        "severity": severity,
                        "start_timestamp": start_ts,
                        "end_timestamp": end_ts,
                        "duration_seconds": round(duration, 2) if end_ts else None,
                        "confidence": 0.90,
                        "detection_method": "RULE_BASED_HEURISTIC",
                        "detection_version": "1.0.0",
                        "explanation": f"Work session was disrupted by {reason} for {round(duration / 60.0, 1)} minutes.",
                        "primary_app": None,
                        "interrupting_app": "system",
                        "resumption_lag_seconds": None,
                        "metadata_payload": {"reason": reason, "event_type": ev.event_type},
                    })

        return results

    def _detect_thrashing(
        self, events: List[NormalizedEvent], user_id: uuid.UUID
    ) -> Tuple[List[Dict[str, Any]], Set[str]]:
        """
        Detects rapid pinballing / context thrashing across multiple applications.
        Condition: >= 4 transitions within 20s across >= 2 unique applications.
        """
        results: List[Dict[str, Any]] = []
        thrash_event_ids: Set[str] = set()

        # Extract only application activation events
        app_events = [
            e for e in events
            if e.event_type == TelemetryEventType.APPLICATION_ACTIVATED.value and e.app_id
        ]

        if len(app_events) < self.config.thrashing_min_switches:
            return results, thrash_event_ids

        i = 0
        while i < len(app_events):
            window_events = [app_events[i]]
            j = i + 1
            while j < len(app_events):
                time_diff = (app_events[j].timestamp - app_events[i].timestamp).total_seconds()
                if time_diff <= self.config.thrashing_window_seconds:
                    window_events.append(app_events[j])
                    j += 1
                else:
                    break

            unique_apps = {e.app_id for e in window_events if e.app_id}
            if (
                len(window_events) >= self.config.thrashing_min_switches
                and len(unique_apps) >= self.config.thrashing_min_unique_apps
            ):
                start_ts = window_events[0].timestamp
                end_ts = window_events[-1].timestamp
                duration = max(1.0, (end_ts - start_ts).total_seconds())
                source_ids = [e.event_id for e in window_events]
                thrash_event_ids.update(source_ids)

                app_chain = " -> ".join([e.app_id for e in window_events[:5]])
                explanation = (
                    f"Rapid attention thrashing detected: {len(window_events)} context switches "
                    f"across {len(unique_apps)} applications ({app_chain}) in {round(duration, 1)} seconds."
                )

                results.append({
                    "user_id": user_id,
                    "source_event_ids": source_ids,
                    "interruption_type": DetectedInterruptionType.CONTEXT_SWITCH,
                    "severity": InterruptionSeverity.HIGH,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "duration_seconds": round(duration, 2),
                    "confidence": 0.88,
                    "detection_method": "RULE_BASED_HEURISTIC",
                    "detection_version": "1.0.0",
                    "explanation": explanation,
                    "primary_app": window_events[0].app_id,
                    "interrupting_app": window_events[-1].app_id,
                    "resumption_lag_seconds": None,
                    "metadata_payload": {
                        "switch_count": len(window_events),
                        "unique_apps_count": len(unique_apps),
                        "apps": list(unique_apps),
                    },
                })
                # Advance past this thrashing cluster
                i = j
            else:
                i += 1

        return results, thrash_event_ids

    def _detect_app_switches(
        self,
        events: List[NormalizedEvent],
        user_id: uuid.UUID,
        excluded_event_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """
        Evaluates application transitions against work context.
        Distinguishes complementary co-working and micro-glances from genuine interruptions.
        """
        results: List[Dict[str, Any]] = []

        # Find application activation intervals
        app_events = [
            e for e in events
            if e.event_type == TelemetryEventType.APPLICATION_ACTIVATED.value
            and e.app_id
            and e.event_id not in excluded_event_ids
        ]

        if len(app_events) < 2:
            return results

        primary_app: Optional[str] = None
        primary_start: Optional[datetime] = None

        for idx in range(len(app_events) - 1):
            curr_ev = app_events[idx]
            next_ev = app_events[idx + 1]

            dwell_time = max(0.0, (next_ev.timestamp - curr_ev.timestamp).total_seconds())

            # Establish primary task focus if not already established
            if primary_app is None:
                if dwell_time >= self.config.primary_task_min_dwell_seconds:
                    primary_app = curr_ev.app_id
                    primary_start = curr_ev.timestamp
                else:
                    continue

            # If user transitions away from established primary app:
            if curr_ev.app_id == primary_app and next_ev.app_id != primary_app:
                diverted_app = next_ev.app_id
                switch_start = next_ev.timestamp

                # Measure how long user stays in diverted app before next event or return
                diverted_dwell = 0.0
                resumed_primary = False
                resumption_ts = None
                return_source_ids = [curr_ev.event_id, next_ev.event_id]

                for k in range(idx + 1, len(app_events)):
                    candidate = app_events[k]
                    return_source_ids.append(candidate.event_id)
                    if k + 1 < len(app_events):
                        k_dwell = (app_events[k + 1].timestamp - candidate.timestamp).total_seconds()
                    else:
                        k_dwell = 0.0

                    if candidate.app_id == primary_app:
                        resumed_primary = True
                        resumption_ts = candidate.timestamp
                        break
                    else:
                        diverted_dwell += k_dwell

                # Rule 1: False Positive Control - Complementary Co-working Pairs
                if self.is_complementary_pair(primary_app, diverted_app):
                    logger.debug(
                        f"Suppressed complementary transition: {primary_app} <-> {diverted_app}"
                    )
                    continue

                # Rule 2: False Positive Control - Micro Switches (< 3.0s)
                if diverted_dwell < self.config.micro_switch_threshold_seconds and resumed_primary:
                    logger.debug(
                        f"Suppressed micro-switch glance ({diverted_dwell:.1f}s) in {diverted_app}"
                    )
                    continue

                # Check if diverted app is high-distraction or diversion exceeds threshold
                is_distraction = diverted_app in self.config.distraction_apps
                if is_distraction or diverted_dwell >= self.config.min_distraction_dwell_seconds:
                    resumption_lag = None
                    if resumed_primary and resumption_ts:
                        # Resumption lag: time between returning to primary app and re-focusing
                        resumption_lag = max(1.0, min(self.config.max_resumption_lag_window_seconds, diverted_dwell * 0.15))

                    severity = self._classify_switch_severity(diverted_dwell, is_distraction, resumption_lag)

                    if resumed_primary:
                        explanation = (
                            f"User transitioned from primary task ({primary_app}) to {diverted_app} "
                            f"for {round(diverted_dwell, 1)} seconds before returning to {primary_app}."
                        )
                        if resumption_lag:
                            explanation += f" (Estimated resumption lag: {round(resumption_lag, 1)}s)."
                    else:
                        explanation = (
                            f"User abandoned primary task ({primary_app}) and switched to {diverted_app} "
                            f"for {round(diverted_dwell, 1)} seconds without resuming primary task."
                        )

                    results.append({
                        "user_id": user_id,
                        "source_event_ids": return_source_ids[:6],
                        "interruption_type": DetectedInterruptionType.APPLICATION_SWITCH,
                        "severity": severity,
                        "start_timestamp": switch_start,
                        "end_timestamp": resumption_ts,
                        "duration_seconds": round(diverted_dwell, 2),
                        "confidence": 0.85 if is_distraction else 0.75,
                        "detection_method": "RULE_BASED_HEURISTIC",
                        "detection_version": "1.0.0",
                        "explanation": explanation,
                        "primary_app": primary_app,
                        "interrupting_app": diverted_app,
                        "resumption_lag_seconds": round(resumption_lag, 2) if resumption_lag else None,
                        "metadata_payload": {
                            "is_distraction_app": is_distraction,
                            "diverted_dwell_seconds": round(diverted_dwell, 2),
                            "returned_to_primary": resumed_primary,
                        },
                    })

                    # If not returned and long dwell, update primary app to new app
                    if not resumed_primary and diverted_dwell >= self.config.primary_task_min_dwell_seconds:
                        primary_app = diverted_app

        return results

    def _classify_idle_severity(self, duration_seconds: float) -> InterruptionSeverity:
        if duration_seconds >= self.config.critical_idle_threshold_seconds:
            return InterruptionSeverity.CRITICAL
        elif duration_seconds >= self.config.long_idle_threshold_seconds:
            return InterruptionSeverity.HIGH
        elif duration_seconds >= 600.0:  # >= 10m
            return InterruptionSeverity.MEDIUM
        return InterruptionSeverity.LOW

    def _classify_switch_severity(
        self, dwell_seconds: float, is_distraction: bool, resumption_lag: Optional[float]
    ) -> InterruptionSeverity:
        if dwell_seconds >= 900.0:
            return InterruptionSeverity.CRITICAL
        elif dwell_seconds >= 300.0 or (is_distraction and dwell_seconds >= 120.0):
            return InterruptionSeverity.HIGH
        elif dwell_seconds >= 60.0 or is_distraction:
            return InterruptionSeverity.MEDIUM
        return InterruptionSeverity.LOW


# ---------------------------------------------------------------------------
# Database Service Integration Layer
# ---------------------------------------------------------------------------

def process_and_persist_telemetry_interruptions(
    db: Session,
    user_id: uuid.UUID,
    raw_events: Sequence[Any],
    detector: Optional[InterruptionDetector] = None,
) -> List[DetectedInterruption]:
    """
    Runs detection on provided telemetry events and persists newly identified
    DetectedInterruption records to PostgreSQL, preventing duplicate detections.
    """
    engine = detector or InterruptionDetector()
    candidates = engine.detect_interruptions(raw_events, user_id)

    persisted: List[DetectedInterruption] = []
    for cand in candidates:
        # Avoid duplicate detections covering the exact same user, start_timestamp, and type
        existing = db.execute(
            select(DetectedInterruption).where(
                DetectedInterruption.user_id == user_id,
                DetectedInterruption.start_timestamp == cand["start_timestamp"],
                DetectedInterruption.interruption_type == cand["interruption_type"],
            )
        ).scalar_one_or_none()

        if existing is not None:
            continue

        interruption = DetectedInterruption(
            user_id=user_id,
            source_event_ids=cand["source_event_ids"],
            interruption_type=cand["interruption_type"],
            severity=cand["severity"],
            start_timestamp=cand["start_timestamp"],
            end_timestamp=cand.get("end_timestamp"),
            duration_seconds=cand.get("duration_seconds"),
            confidence=cand.get("confidence", 1.0),
            detection_method=cand.get("detection_method", "RULE_BASED_HEURISTIC"),
            detection_version=cand.get("detection_version", "1.0.0"),
            explanation=cand["explanation"],
            primary_app=cand.get("primary_app"),
            interrupting_app=cand.get("interrupting_app"),
            resumption_lag_seconds=cand.get("resumption_lag_seconds"),
            metadata_payload=cand.get("metadata_payload", {}),
        )
        db.add(interruption)
        persisted.append(interruption)

    if persisted:
        db.commit()
        for item in persisted:
            db.refresh(item)

    return persisted


def query_detected_interruptions(
    db: Session,
    user_id: uuid.UUID,
    interruption_type: Optional[DetectedInterruptionType] = None,
    severity: Optional[InterruptionSeverity] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    min_confidence: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[DetectedInterruption], int]:
    """Retrieves paginated and filtered detected interruptions for a user."""
    stmt = select(DetectedInterruption).where(DetectedInterruption.user_id == user_id)

    if interruption_type:
        stmt = stmt.where(DetectedInterruption.interruption_type == interruption_type)
    if severity:
        stmt = stmt.where(DetectedInterruption.severity == severity)
    if start_time:
        stmt = stmt.where(DetectedInterruption.start_timestamp >= start_time)
    if end_time:
        stmt = stmt.where(DetectedInterruption.start_timestamp <= end_time)
    if min_confidence is not None:
        stmt = stmt.where(DetectedInterruption.confidence >= min_confidence)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Paginate and order by newest first
    stmt = stmt.order_by(desc(DetectedInterruption.start_timestamp)).limit(limit).offset(offset)
    items = list(db.scalars(stmt).all())

    return items, total


def get_detected_interruption_by_id(
    db: Session, user_id: uuid.UUID, interruption_id: uuid.UUID
) -> Optional[DetectedInterruption]:
    """Fetches a specific detected interruption verifying user ownership."""
    return db.execute(
        select(DetectedInterruption).where(
            DetectedInterruption.id == interruption_id,
            DetectedInterruption.user_id == user_id,
        )
    ).scalar_one_or_none()


def submit_interruption_feedback(
    db: Session,
    user_id: uuid.UUID,
    interruption_id: uuid.UUID,
    payload: DetectedInterruptionFeedbackCreate,
) -> DetectedInterruptionFeedback:
    """Submits ground-truth user feedback on a detected interruption."""
    interruption = get_detected_interruption_by_id(db, user_id, interruption_id)
    if not interruption:
        raise ValueError(f"Detected interruption {interruption_id} not found for this user.")

    feedback = DetectedInterruptionFeedback(
        interruption_id=interruption_id,
        user_id=user_id,
        feedback_classification=payload.feedback_classification,
        notes=payload.notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def compute_interruption_metrics(
    db: Session, user_id: uuid.UUID
) -> InterruptionDetectionMetricsResponse:
    """Computes behavioral interruption metrics and feedback validation scores."""
    # Total detected
    interruptions = db.scalars(
        select(DetectedInterruption).where(DetectedInterruption.user_id == user_id)
    ).all()

    total_detected = len(interruptions)
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    durations: List[float] = []
    lags: List[float] = []

    for item in interruptions:
        t_key = item.interruption_type.value if hasattr(item.interruption_type, "value") else str(item.interruption_type)
        s_key = item.severity.value if hasattr(item.severity, "value") else str(item.severity)
        by_type[t_key] = by_type.get(t_key, 0) + 1
        by_severity[s_key] = by_severity.get(s_key, 0) + 1

        if item.duration_seconds is not None:
            durations.append(item.duration_seconds)
        if item.resumption_lag_seconds is not None:
            lags.append(item.resumption_lag_seconds)

    # Feedback analytics
    feedback_records = db.scalars(
        select(DetectedInterruptionFeedback).where(DetectedInterruptionFeedback.user_id == user_id)
    ).all()

    total_feedback = len(feedback_records)
    feedback_breakdown: Dict[str, int] = {}
    genuine_count = 0
    false_positive_count = 0

    for fb in feedback_records:
        cls_key = (
            fb.feedback_classification.value
            if hasattr(fb.feedback_classification, "value")
            else str(fb.feedback_classification)
        )
        feedback_breakdown[cls_key] = feedback_breakdown.get(cls_key, 0) + 1

        if fb.feedback_classification == InterruptionFeedbackClassification.GENUINE_INTERRUPTION:
            genuine_count += 1
        elif fb.feedback_classification in (
            InterruptionFeedbackClassification.INTENTIONAL_SWITCH,
            InterruptionFeedbackClassification.INCORRECT_DETECTION,
        ):
            false_positive_count += 1

    accuracy_rate = (genuine_count / total_feedback) if total_feedback > 0 else None
    false_positive_rate = (false_positive_count / total_feedback) if total_feedback > 0 else None
    avg_duration = (sum(durations) / len(durations)) if durations else None
    avg_lag = (sum(lags) / len(lags)) if lags else None

    return InterruptionDetectionMetricsResponse(
        total_detected=total_detected,
        by_type=by_type,
        by_severity=by_severity,
        total_feedback_count=total_feedback,
        feedback_breakdown=feedback_breakdown,
        accuracy_rate=round(accuracy_rate, 4) if accuracy_rate is not None else None,
        false_positive_rate=round(false_positive_rate, 4) if false_positive_rate is not None else None,
        average_duration_seconds=round(avg_duration, 2) if avg_duration is not None else None,
        average_resumption_lag_seconds=round(avg_lag, 2) if avg_lag is not None else None,
    )
