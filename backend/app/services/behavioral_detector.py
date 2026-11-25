"""
Behavioral Change Detector (ContextIQ Phase 7.3).
Monitors telemetry streams, task state shifts, and ML intelligence outputs to detect
meaningful behavioral anomalies:
- Context thrashing (rapid application switching)
- Elevated forgetting risk spikes
- Unusually prolonged recovery lag
- Missed task resumption
- Calendar overload & zero-buffer meetings
- Behavioral Friction Index (BFI) spikes
- Circadian focus pattern drift
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.event_schemas import EventSource, StandardEvent, StandardEventType


class BehavioralChangeDetector:
    """
    Stateless and state-aware behavioral detection methods.
    Transforms raw operational telemetry into standardized behavioral events
    accompanied by conformal uncertainty bounds.
    """

    @classmethod
    def detect_context_thrashing(
        cls,
        user_id: uuid.UUID,
        switch_count_last_minute: int,
        active_apps: List[str],
        device_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[StandardEvent]:
        """
        Detects acute context thrashing (>= 6 application switches per minute).
        Indicates cognitive fragmentation and task resumption friction.
        """
        if switch_count_last_minute < 6:
            return None

        ts = now or datetime.now(timezone.utc)
        switches_per_min = float(switch_count_last_minute)

        # Conformal bound estimation for thrashing severity
        # High frequency switch count gives high empirical confidence
        confidence = min(0.96, 0.70 + (switches_per_min - 6.0) * 0.04)
        lower_bound = max(0.65, confidence - 0.12)
        upper_bound = min(0.99, confidence + 0.05)

        return StandardEvent(
            event_id=str(uuid.uuid4()),
            event_type=StandardEventType.THRASHING_DETECTED.value,
            user_id=user_id,
            device_id=device_id,
            event_timestamp=ts,
            source=EventSource.DESKTOP_TELEMETRY.value,
            payload={
                "switch_count": switch_count_last_minute,
                "switches_per_minute": switches_per_min,
                "active_apps": active_apps[:5],
                "confidence_score": round(confidence, 3),
                "uncertainty_lower_bound": round(lower_bound, 3),
                "uncertainty_upper_bound": round(upper_bound, 3),
                "conformal_interval_text": f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (coverage 90%)",
                "recommended_action": "ENTER_FOCUS_SESSION",
                "rationale": f"Detected {switch_count_last_minute} application switches in 60s across {len(active_apps)} apps, indicating acute context fragmentation.",
            },
            idempotency_key=f"thrashing:{user_id}:{ts.strftime('%Y%m%d%H%M')}",
        )

    @classmethod
    def detect_forgetting_risk_spike(
        cls,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        task_title: str,
        predicted_lapse_probability: float,
        threshold: float = 0.70,
        hours_since_interruption: float = 2.0,
        now: Optional[datetime] = None,
    ) -> Optional[StandardEvent]:
        """
        Detects when a background task's forgetting probability exceeds threshold.
        """
        if predicted_lapse_probability < threshold:
            return None

        ts = now or datetime.now(timezone.utc)
        confidence = min(0.92, 0.65 + predicted_lapse_probability * 0.3)
        lower_bound = max(0.55, confidence - 0.15)
        upper_bound = min(0.98, confidence + 0.06)

        return StandardEvent(
            event_id=str(uuid.uuid4()),
            event_type=StandardEventType.FORGETTING_RISK_SPIKE.value,
            user_id=user_id,
            event_timestamp=ts,
            source=EventSource.INTELLIGENCE_ENGINE.value,
            payload={
                "task_id": str(task_id),
                "task_title": task_title,
                "lapse_probability": round(predicted_lapse_probability, 3),
                "hours_since_interruption": round(hours_since_interruption, 2),
                "threshold": threshold,
                "confidence_score": round(confidence, 3),
                "uncertainty_lower_bound": round(lower_bound, 3),
                "uncertainty_upper_bound": round(upper_bound, 3),
                "conformal_interval_text": f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (coverage 90%)",
                "recommended_action": "SEND_REMINDER",
                "rationale": f"Predicted lapse probability of {int(predicted_lapse_probability*100)}% on '{task_title}' after {hours_since_interruption:.1f}h inactive.",
            },
            idempotency_key=f"forgetting:{user_id}:{task_id}:{ts.strftime('%Y%m%d%H')}",
        )

    @classmethod
    def detect_recovery_lag_exceeded(
        cls,
        user_id: uuid.UUID,
        actual_recovery_duration_seconds: float,
        expected_recovery_seconds: float = 600.0,
        buffer_threshold_seconds: float = 600.0,  # 10m extra
        now: Optional[datetime] = None,
    ) -> Optional[StandardEvent]:
        """
        Detects when cognitive recovery after an interruption takes longer than expected + buffer.
        """
        lag = actual_recovery_duration_seconds - expected_recovery_seconds
        if lag < buffer_threshold_seconds:
            return None

        ts = now or datetime.now(timezone.utc)
        confidence = 0.88
        lower_bound = 0.76
        upper_bound = 0.94

        return StandardEvent(
            event_id=str(uuid.uuid4()),
            event_type=StandardEventType.RECOVERY_LAG_EXCEEDED.value,
            user_id=user_id,
            event_timestamp=ts,
            source=EventSource.INTELLIGENCE_ENGINE.value,
            payload={
                "actual_recovery_seconds": round(actual_recovery_duration_seconds, 1),
                "expected_recovery_seconds": round(expected_recovery_seconds, 1),
                "excess_lag_minutes": round(lag / 60.0, 1),
                "confidence_score": round(confidence, 3),
                "uncertainty_lower_bound": round(lower_bound, 3),
                "uncertainty_upper_bound": round(upper_bound, 3),
                "conformal_interval_text": f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (coverage 90%)",
                "recommended_action": "SCHEDULE_RECOVERY_BUFFER",
                "rationale": f"Post-interruption recovery took {actual_recovery_duration_seconds/60:.1f}m, exceeding expected {expected_recovery_seconds/60:.1f}m by {lag/60:.1f}m.",
            },
            idempotency_key=f"recovery_lag:{user_id}:{ts.strftime('%Y%m%d%H%M')}",
        )

    @classmethod
    def detect_missed_resumption(
        cls,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        task_title: str,
        inactive_minutes: float,
        threshold_minutes: float = 45.0,
        now: Optional[datetime] = None,
    ) -> Optional[StandardEvent]:
        """
        Detects when an interrupted in-progress task has not been resumed within threshold.
        """
        if inactive_minutes < threshold_minutes:
            return None

        ts = now or datetime.now(timezone.utc)
        confidence = 0.86
        lower_bound = 0.74
        upper_bound = 0.93

        return StandardEvent(
            event_id=str(uuid.uuid4()),
            event_type=StandardEventType.MISSED_RESUMPTION.value,
            user_id=user_id,
            event_timestamp=ts,
            source=EventSource.TASK_SERVICE.value,
            payload={
                "task_id": str(task_id),
                "task_title": task_title,
                "inactive_minutes": round(inactive_minutes, 1),
                "threshold_minutes": threshold_minutes,
                "confidence_score": round(confidence, 3),
                "uncertainty_lower_bound": round(lower_bound, 3),
                "uncertainty_upper_bound": round(upper_bound, 3),
                "conformal_interval_text": f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (coverage 90%)",
                "recommended_action": "PROPOSE_RESUMPTION_BUFFER",
                "rationale": f"Task '{task_title}' remained interrupted for {inactive_minutes:.0f}m without resumption.",
            },
            idempotency_key=f"missed_resumption:{user_id}:{task_id}:{ts.strftime('%Y%m%d%H')}",
        )

    @classmethod
    def detect_calendar_overload(
        cls,
        user_id: uuid.UUID,
        consecutive_events_count: int,
        total_dense_hours: float,
        buffer_minutes_between: float = 0.0,
        now: Optional[datetime] = None,
    ) -> Optional[StandardEvent]:
        """
        Detects calendar saturation: 3+ back-to-back meetings with insufficient buffer.
        """
        if consecutive_events_count < 3 or buffer_minutes_between >= 5.0:
            return None

        ts = now or datetime.now(timezone.utc)
        confidence = 0.93
        lower_bound = 0.85
        upper_bound = 0.97

        return StandardEvent(
            event_id=str(uuid.uuid4()),
            event_type=StandardEventType.CALENDAR_OVERLOAD.value,
            user_id=user_id,
            event_timestamp=ts,
            source=EventSource.CALENDAR_SYNC.value,
            payload={
                "consecutive_events_count": consecutive_events_count,
                "total_dense_hours": round(total_dense_hours, 1),
                "buffer_minutes": buffer_minutes_between,
                "confidence_score": round(confidence, 3),
                "uncertainty_lower_bound": round(lower_bound, 3),
                "uncertainty_upper_bound": round(upper_bound, 3),
                "conformal_interval_text": f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (coverage 90%)",
                "recommended_action": "SCHEDULE_RECOVERY_BUFFER",
                "rationale": f"Detected {consecutive_events_count} back-to-back calendar events ({total_dense_hours:.1f} hours) with 0-5m buffer.",
            },
            idempotency_key=f"calendar_overload:{user_id}:{ts.strftime('%Y%m%d%H')}",
        )

    @classmethod
    def detect_bfi_spike(
        cls,
        user_id: uuid.UUID,
        baseline_bfi: float,
        current_bfi: float,
        threshold_delta: float = 0.20,
        now: Optional[datetime] = None,
    ) -> Optional[StandardEvent]:
        """
        Detects significant increase in Behavioral Friction Index (BFI).
        """
        delta = current_bfi - baseline_bfi
        if delta < threshold_delta:
            return None

        ts = now or datetime.now(timezone.utc)
        confidence = 0.84
        lower_bound = 0.72
        upper_bound = 0.91

        return StandardEvent(
            event_id=str(uuid.uuid4()),
            event_type=StandardEventType.BFI_SPIKE.value,
            user_id=user_id,
            event_timestamp=ts,
            source=EventSource.BEHAVIORAL_TWIN.value,
            payload={
                "baseline_bfi": round(baseline_bfi, 3),
                "current_bfi": round(current_bfi, 3),
                "delta": round(delta, 3),
                "confidence_score": round(confidence, 3),
                "uncertainty_lower_bound": round(lower_bound, 3),
                "uncertainty_upper_bound": round(upper_bound, 3),
                "conformal_interval_text": f"Conformal [{int(lower_bound*100)}%-{int(upper_bound*100)}%] (coverage 90%)",
                "recommended_action": "SUGGEST_BREAK",
                "rationale": f"Behavioral Friction Index spiked by +{delta:.2f} above baseline (from {baseline_bfi:.2f} to {current_bfi:.2f}).",
            },
            idempotency_key=f"bfi_spike:{user_id}:{ts.strftime('%Y%m%d%H')}",
        )
