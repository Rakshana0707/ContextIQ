"""
Behavioral Sequence Preprocessor & Feature Tokenizer (ContextIQ Phase 6.5).

Implements:
1. Standardized event tokenization and vocabulary mapping.
2. Leakage-safe chronological sorting and validation (t <= t_pred).
3. Temporal feature encoding (log-relative delta, cyclic circadian hour, normalized friction).
4. Sequence padding and attention mask generation.
5. Tabular summary feature extraction for fair baseline comparison.
6. Synthetic multi-user sequence generator for reproducible benchmarking.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch

from app.schemas.temporal_sequence import (
    BehavioralEventToken,
    BehavioralSequence,
    SequenceEventType,
    SequencePredictionTarget,
)

logger = logging.getLogger(__name__)

# Standard Token Vocabularies
EVENT_TYPE_TO_ID: Dict[SequenceEventType, int] = {
    SequenceEventType.PAD: 0,
    SequenceEventType.UNK: 1,
    SequenceEventType.TASK_CREATE: 2,
    SequenceEventType.TASK_START: 3,
    SequenceEventType.TASK_PAUSE: 4,
    SequenceEventType.TASK_RESUME: 5,
    SequenceEventType.TASK_COMPLETE: 6,
    SequenceEventType.APPLICATION_SWITCH: 7,
    SequenceEventType.INTERRUPTION_DETECTED: 8,
    SequenceEventType.RECOVERY_BUFFER_DISPATCH: 9,
    SequenceEventType.NOTIFICATION_DELIVERED: 10,
    SequenceEventType.NOTIFICATION_DISMISSED: 11,
    SequenceEventType.CALENDAR_MEETING_START: 12,
    SequenceEventType.CALENDAR_MEETING_END: 13,
    SequenceEventType.FOCUS_WINDOW_START: 14,
    SequenceEventType.FOCUS_WINDOW_END: 15,
    SequenceEventType.IDLE_TIMEOUT: 16,
}

CATEGORY_TO_ID: Dict[str, int] = {
    "General": 0,
    "Coding": 1,
    "DeepWork": 2,
    "Admin": 3,
    "Meeting": 4,
    "Communication": 5,
}

SEVERITY_TO_ID: Dict[str, int] = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class SequencePreprocessor:
    """
    Transforms raw chronological event histories into padded tensor representations
    and tabular feature summaries with zero temporal leakage.
    """

    MAX_SEQ_LEN: int = 32
    VOCAB_SIZE: int = len(EVENT_TYPE_TO_ID)
    CONTINUOUS_FEATURE_DIM: int = 6  # log_delta_t, log_dur, sin_hr, cos_hr, norm_bfi, norm_switches

    @classmethod
    def process_sequence(
        cls,
        sequence: BehavioralSequence,
        max_seq_len: int = 32,
    ) -> Dict[str, Any]:
        """
        Converts a BehavioralSequence into PyTorch tensor inputs and a tabular summary vector.
        """
        raw_events = sequence.events
        pred_ts = sequence.prediction_timestamp

        # 1. Anti-leakage verification: Ensure all events are strictly t <= t_pred
        # Sort chronologically
        events = sorted(raw_events, key=lambda e: e.relative_timestamp_seconds)
        n_events = len(events)

        # Truncate to most recent max_seq_len events if longer
        if n_events > max_seq_len:
            events = events[-max_seq_len:]
            n_events = max_seq_len

        token_ids = np.zeros(max_seq_len, dtype=np.int64)  # 0 is <PAD>
        category_ids = np.zeros(max_seq_len, dtype=np.int64)
        severity_ids = np.zeros(max_seq_len, dtype=np.int64)
        continuous_features = np.zeros((max_seq_len, cls.CONTINUOUS_FEATURE_DIM), dtype=np.float32)
        attention_mask = np.zeros(max_seq_len, dtype=np.float32)

        prev_t = 0.0
        for i, ev in enumerate(events):
            t_id = EVENT_TYPE_TO_ID.get(ev.event_type, EVENT_TYPE_TO_ID[SequenceEventType.UNK])
            cat_id = CATEGORY_TO_ID.get(ev.task_category, 0)
            sev_id = SEVERITY_TO_ID.get(ev.interruption_severity, 0)

            cur_t = ev.relative_timestamp_seconds
            delta_t = max(0.0, cur_t - prev_t)
            prev_t = cur_t

            # Feature encodings
            log_delta = math.log1p(delta_t)
            log_dur = math.log1p(max(0.0, ev.duration_seconds))
            hr_rad = (ev.hour_of_day / 24.0) * 2.0 * math.pi
            sin_hr = math.sin(hr_rad)
            cos_hr = math.cos(hr_rad)
            norm_bfi = max(0.0, min(1.0, ev.rolling_bfi / 100.0))
            norm_switches = min(1.0, ev.recent_switch_count / 10.0)

            token_ids[i] = t_id
            category_ids[i] = cat_id
            severity_ids[i] = sev_id
            continuous_features[i] = [log_delta, log_dur, sin_hr, cos_hr, norm_bfi, norm_switches]
            attention_mask[i] = 1.0  # 1 for observed event

        # 2. Extract Tabular Baseline Summary Vector
        tabular_vector = cls._extract_tabular_features(events, n_events)

        return {
            "token_ids": torch.tensor(token_ids, dtype=torch.long),
            "category_ids": torch.tensor(category_ids, dtype=torch.long),
            "severity_ids": torch.tensor(severity_ids, dtype=torch.long),
            "continuous_features": torch.tensor(continuous_features, dtype=torch.float32),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.float32),
            "sequence_length": n_events,
            "tabular_vector": tabular_vector,
            "is_cold_start": bool(n_events < 5),
        }

    @classmethod
    def _extract_tabular_features(
        cls,
        events: List[BehavioralEventToken],
        seq_len: int,
    ) -> np.ndarray:
        """
        Extracts aggregated summary features (mean friction, switch count, event frequency)
        for fair comparison against non-sequential tabular baselines.
        """
        if not events:
            return np.zeros(12, dtype=np.float32)

        bfi_vals = [e.rolling_bfi for e in events]
        durs = [e.duration_seconds for e in events]
        switches = [e.recent_switch_count for e in events]

        n_interruptions = sum(1 for e in events if e.event_type == SequenceEventType.INTERRUPTION_DETECTED)
        n_switches = sum(1 for e in events if e.event_type == SequenceEventType.APPLICATION_SWITCH)
        n_meetings = sum(1 for e in events if e.event_type == SequenceEventType.CALENDAR_MEETING_START)
        n_pauses = sum(1 for e in events if e.event_type == SequenceEventType.TASK_PAUSE)

        last_ev = events[-1]
        last_event_id = EVENT_TYPE_TO_ID.get(last_ev.event_type, 1)

        vec = np.array([
            float(seq_len),
            float(np.mean(bfi_vals)),
            float(np.std(bfi_vals)),
            float(np.mean(durs)),
            float(np.sum(durs)),
            float(np.mean(switches)),
            float(n_interruptions),
            float(n_switches),
            float(n_meetings),
            float(n_pauses),
            float(last_ev.hour_of_day),
            float(last_event_id),
        ], dtype=np.float32)
        return vec

    # -----------------------------------------------------------------------
    # Synthetic Multi-User Benchmark Generator
    # -----------------------------------------------------------------------

    @classmethod
    def generate_benchmark_sequences(
        cls,
        n_sequences: int = 300,
        n_users: int = 20,
        seed: int = 42,
    ) -> Tuple[List[BehavioralSequence], Dict[SequencePredictionTarget, np.ndarray]]:
        """
        Generates realistic chronological event sequences across distinct users with
        well-defined behavioral dependencies for all 5 prediction targets.
        """
        rng = np.random.RandomState(seed)
        user_ids = [uuid.uuid4() for _ in range(n_users)]

        sequences: List[BehavioralSequence] = []
        labels: Dict[SequencePredictionTarget, List[int]] = {
            target: [] for target in SequencePredictionTarget
        }

        now_base = datetime(2026, 11, 25, 9, 0, 0, tzinfo=timezone.utc)

        for seq_i in range(n_sequences):
            u_id = user_ids[seq_i % n_users]
            seq_len = rng.randint(3, cls.MAX_SEQ_LEN)
            t_pred = now_base + timedelta(minutes=seq_i * 15)

            events: List[BehavioralEventToken] = []
            cur_time = 0.0
            cur_bfi = rng.normal(45.0, 10.0)

            for step in range(seq_len):
                delta_t = rng.exponential(scale=120.0) + 10.0
                cur_time += delta_t
                dur = rng.exponential(scale=60.0) if rng.uniform(0, 1) < 0.4 else 0.0

                # Transition logic: Elevated friction increases probability of interruptions
                if cur_bfi > 65.0 and rng.uniform(0, 1) < 0.5:
                    ev_type = SequenceEventType.INTERRUPTION_DETECTED
                    sev = "HIGH"
                    cur_bfi = min(95.0, cur_bfi + 5.0)
                elif rng.uniform(0, 1) < 0.25:
                    ev_type = SequenceEventType.APPLICATION_SWITCH
                    sev = "NONE"
                    cur_bfi = min(90.0, cur_bfi + 2.0)
                elif rng.uniform(0, 1) < 0.15:
                    ev_type = SequenceEventType.RECOVERY_BUFFER_DISPATCH
                    sev = "NONE"
                    cur_bfi = max(20.0, cur_bfi - 8.0)
                elif rng.uniform(0, 1) < 0.10:
                    ev_type = SequenceEventType.CALENDAR_MEETING_START
                    sev = "MEDIUM"
                else:
                    task_types = [
                        SequenceEventType.TASK_START,
                        SequenceEventType.TASK_RESUME,
                        SequenceEventType.TASK_PAUSE,
                        SequenceEventType.NOTIFICATION_DELIVERED,
                    ]
                    ev_type = task_types[rng.randint(0, len(task_types))]
                    sev = "NONE"

                cat_choices = ["Coding", "DeepWork", "Admin", "General"]
                cat_val = cat_choices[rng.randint(0, len(cat_choices))]

                events.append(
                    BehavioralEventToken(
                        event_type=ev_type,
                        relative_timestamp_seconds=round(cur_time, 1),
                        duration_seconds=round(dur, 1),
                        task_category=cat_val,
                        interruption_severity=sev,
                        rolling_bfi=round(float(cur_bfi), 1),
                        recent_switch_count=int(rng.poisson(lam=2.0)),
                        hour_of_day=int((9 + (seq_i // 4)) % 24),
                    )
                )

            seq = BehavioralSequence(
                user_id=u_id,
                prediction_timestamp=t_pred,
                events=events,
                sequence_length=seq_len,
                is_cold_start=bool(seq_len < 5),
            )
            sequences.append(seq)

            # Generate Ground-Truth Targets based on sequence dynamics
            last_ev = events[-1]
            avg_bfi = float(np.mean([e.rolling_bfi for e in events]))
            n_ints = sum(1 for e in events if e.event_type == SequenceEventType.INTERRUPTION_DETECTED)

            # 1. Short-term task resumption: Low friction + recovery buffer -> high resumption
            p_resume = 0.70 - 0.005 * (avg_bfi - 45.0) - 0.05 * n_ints
            labels[SequencePredictionTarget.SHORT_TERM_TASK_RESUMPTION].append(
                int(rng.uniform(0, 1) < np.clip(p_resume, 0.05, 0.95))
            )

            # 2. Interruption recovery risk: Frequent disruptions -> high recovery lag
            p_risk = 0.20 + 0.008 * (avg_bfi - 45.0) + 0.10 * n_ints
            labels[SequencePredictionTarget.INTERRUPTION_RECOVERY_RISK].append(
                int(rng.uniform(0, 1) < np.clip(p_risk, 0.05, 0.95))
            )

            # 3. Future context switch: Application switch near end -> high future switch
            p_switch = 0.35 + 0.15 * (1 if last_ev.event_type == SequenceEventType.APPLICATION_SWITCH else 0)
            labels[SequencePredictionTarget.FUTURE_CONTEXT_SWITCH].append(
                int(rng.uniform(0, 1) < np.clip(p_switch, 0.05, 0.95))
            )

            # 4. Task completion: Longer sequences with low friction -> high completion
            p_comp = 0.50 + 0.01 * seq_len - 0.004 * (avg_bfi - 45.0)
            labels[SequencePredictionTarget.TASK_COMPLETION].append(
                int(rng.uniform(0, 1) < np.clip(p_comp, 0.05, 0.95))
            )

            # 5. Friction trend: Compare first half vs second half
            half = max(1, seq_len // 2)
            first_bfi = np.mean([e.rolling_bfi for e in events[:half]])
            second_bfi = np.mean([e.rolling_bfi for e in events[half:]])
            if second_bfi > first_bfi + 4.0:
                trend = 0  # INCREASING
            elif second_bfi < first_bfi - 4.0:
                trend = 1  # DECREASING
            else:
                trend = 2  # STABLE
            labels[SequencePredictionTarget.BEHAVIORAL_FRICTION_TREND].append(trend)

        array_labels = {k: np.array(v) for k, v in labels.items()}
        return sequences, array_labels
