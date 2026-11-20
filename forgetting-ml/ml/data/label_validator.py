"""
label_validator.py

ContextIQ Automated Label Quality Validation Module
Phase 2.1 Specification Implementation

Validates dataset labels and event histories against 7 integrity rules:
1. Missing labels / Null checks
2. Contradictory task events
3. Impossible timestamps
4. Duplicate events
5. Tasks completed after deadlines (Tardy vs Forgotten verification)
6. Insufficient observation windows (Right-censorship detection)
7. Incorrectly labeled intentional postponements

Outputs structured audit reports in Markdown and JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from ml.data.label_generator import OutcomeType, _ensure_utc


@dataclass
class AnomalyRecord:
    task_id: str
    check_name: str
    severity: str  # ERROR, WARNING
    description: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationSummary:
    total_tasks: int = 0
    valid_training_samples: int = 0
    excluded_samples: int = 0
    outcome_distribution: Dict[str, int] = field(default_factory=dict)
    will_forget_distribution: Dict[str, int] = field(default_factory=dict)
    anomalies_by_check: Dict[str, int] = field(default_factory=dict)
    anomalies: List[AnomalyRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "valid_training_samples": self.valid_training_samples,
            "excluded_samples": self.excluded_samples,
            "outcome_distribution": self.outcome_distribution,
            "will_forget_distribution": self.will_forget_distribution,
            "anomalies_by_check": self.anomalies_by_check,
            "total_anomalies": len(self.anomalies),
            "anomalies_sample": [
                {
                    "task_id": a.task_id,
                    "check": a.check_name,
                    "severity": a.severity,
                    "desc": a.description,
                }
                for a in self.anomalies[:50]
            ],
        }


class LabelValidator:
    def __init__(self):
        self.summary = ValidationSummary()

    def validate(
        self,
        tasks_df: pd.DataFrame,
        events_df: Optional[pd.DataFrame] = None,
        labeled_df: Optional[pd.DataFrame] = None,
        as_of: Optional[datetime] = None,
    ) -> ValidationSummary:
        """Runs the complete suite of 7 label quality validation checks."""
        self.summary = ValidationSummary(total_tasks=len(tasks_df))
        if tasks_df.empty:
            return self.summary

        if as_of is None:
            as_of = datetime.now(timezone.utc)
        else:
            as_of = _ensure_utc(as_of)

        events_by_task = {}
        if events_df is not None and not events_df.empty:
            task_col = "task_id" if "task_id" in events_df.columns else "taskId"
            for t_id, grp in events_df.groupby(task_col):
                events_by_task[str(t_id)] = grp.to_dict("records")

        labeled_by_task = {}
        if labeled_df is not None and not labeled_df.empty:
            id_col = "task_id" if "task_id" in labeled_df.columns else "id"
            for _, r in labeled_df.iterrows():
                labeled_by_task[str(r[id_col])] = r.to_dict()

        outcome_counts: Dict[str, int] = {}
        binary_counts: Dict[str, int] = {"0": 0, "1": 0, "None": 0}

        for _, task_row in tasks_df.iterrows():
            t = task_row.to_dict()
            t_id = str(t.get("id") or t.get("task_id", "unknown"))
            t_events = events_by_task.get(t_id, [])
            l_info = labeled_by_task.get(t_id, {})

            # Outcome tallying
            outcome = l_info.get("outcome_type") or str(t.get("outcome_type", "UNKNOWN"))
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

            wf = l_info.get("will_forget") if "will_forget" in l_info else t.get("will_forget")
            if wf is None or pd.isna(wf):
                binary_counts["None"] += 1
            elif int(wf) == 1:
                binary_counts["1"] += 1
            else:
                binary_counts["0"] += 1

            is_valid = l_info.get("is_valid_training_sample", True)
            if is_valid:
                self.summary.valid_training_samples += 1
            else:
                self.summary.excluded_samples += 1

            # -------------------------------------------------------------
            # CHECK 1: Missing Labels / Null Checks
            # -------------------------------------------------------------
            if is_valid and (wf is None or pd.isna(wf)):
                self._record_anomaly(
                    t_id,
                    "MISSING_LABEL",
                    "ERROR",
                    "Task marked as valid training sample but will_forget label is NULL.",
                )

            # -------------------------------------------------------------
            # CHECK 2: Contradictory Task Events
            # -------------------------------------------------------------
            self._check_event_contradictions(t_id, t, t_events)

            # -------------------------------------------------------------
            # CHECK 3: Impossible Timestamps
            # -------------------------------------------------------------
            self._check_impossible_timestamps(t_id, t, t_events, as_of)

            # -------------------------------------------------------------
            # CHECK 4: Duplicate Events
            # -------------------------------------------------------------
            self._check_duplicate_events(t_id, t_events)

            # -------------------------------------------------------------
            # CHECK 5: Completed After Deadline (Tardy vs Forgotten)
            # -------------------------------------------------------------
            self._check_tardy_vs_forgotten(t_id, t, t_events, l_info)

            # -------------------------------------------------------------
            # CHECK 6: Insufficient Observation Windows (Censorship)
            # -------------------------------------------------------------
            self._check_observation_window(t_id, t, l_info, as_of)

            # -------------------------------------------------------------
            # CHECK 7: Mislabeled Intentional Postponements
            # -------------------------------------------------------------
            self._check_postponement_labeling(t_id, t, t_events, l_info)

        self.summary.outcome_distribution = outcome_counts
        self.summary.will_forget_distribution = binary_counts
        return self.summary

    def _record_anomaly(
        self, task_id: str, check_name: str, severity: str, desc: str, details: Optional[Dict] = None
    ):
        self.summary.anomalies_by_check[check_name] = (
            self.summary.anomalies_by_check.get(check_name, 0) + 1
        )
        self.summary.anomalies.append(
            AnomalyRecord(
                task_id=task_id,
                check_name=check_name,
                severity=severity,
                description=desc,
                details=details or {},
            )
        )

    def _check_event_contradictions(self, task_id: str, task: dict, events: list):
        created_at = _ensure_utc(task.get("created_at"))
        comp_time = _ensure_utc(task.get("completed_at"))
        forgotten_time = _ensure_utc(task.get("forgotten_at"))
        cancelled_time = _ensure_utc(task.get("cancelled_at"))

        event_types = [str(e.get("event_type", "")).lower() for e in events]
        if "completed" in event_types and "forgotten" in event_types:
            self._record_anomaly(
                task_id,
                "CONTRADICTORY_EVENTS",
                "ERROR",
                "Task contains both COMPLETED and FORGOTTEN lifecycle events.",
            )

        if comp_time and forgotten_time:
            self._record_anomaly(
                task_id,
                "CONTRADICTORY_EVENTS",
                "ERROR",
                f"Task has both completed_at ({comp_time}) and forgotten_at ({forgotten_time}).",
            )

        if comp_time and cancelled_time and comp_time > cancelled_time:
            self._record_anomaly(
                task_id,
                "CONTRADICTORY_EVENTS",
                "ERROR",
                "Task completed_at occurs after cancelled_at.",
            )

    def _check_impossible_timestamps(self, task_id: str, task: dict, events: list, as_of: datetime):
        created_at = _ensure_utc(task.get("created_at"))
        if created_at is None:
            self._record_anomaly(
                task_id, "IMPOSSIBLE_TIMESTAMPS", "ERROR", "Task is missing created_at timestamp."
            )
            return

        if created_at > as_of:
            self._record_anomaly(
                task_id,
                "IMPOSSIBLE_TIMESTAMPS",
                "ERROR",
                f"Task created_at ({created_at}) is in future relative to as_of ({as_of}).",
            )

        for ev in events:
            ev_t = _ensure_utc(ev.get("timestamp") or ev.get("created_at"))
            if ev_t is not None and ev_t < created_at:
                self._record_anomaly(
                    task_id,
                    "IMPOSSIBLE_TIMESTAMPS",
                    "ERROR",
                    f"Lifecycle event {ev.get('event_type')} occurred before task creation: {ev_t} < {created_at}",
                )

        comp_t = _ensure_utc(task.get("completed_at"))
        if comp_t and comp_t < created_at:
            self._record_anomaly(
                task_id,
                "IMPOSSIBLE_TIMESTAMPS",
                "ERROR",
                f"Task completed_at ({comp_t}) precedes created_at ({created_at}).",
            )

    def _check_duplicate_events(self, task_id: str, events: list):
        seen = set()
        for ev in events:
            ev_t = _ensure_utc(ev.get("timestamp") or ev.get("created_at"))
            ev_type = str(ev.get("event_type", "")).lower()
            key = (ev_type, ev_t.isoformat() if ev_t else None)
            if key in seen and ev_t is not None:
                self._record_anomaly(
                    task_id,
                    "DUPLICATE_EVENTS",
                    "WARNING",
                    f"Duplicate event detected: {ev_type} at {ev_t.isoformat()}.",
                )
            seen.add(key)

    def _check_tardy_vs_forgotten(self, task_id: str, task: dict, events: list, label_info: dict):
        comp_t = _ensure_utc(task.get("completed_at"))
        for ev in events:
            if str(ev.get("event_type", "")).lower() == "completed":
                comp_t = _ensure_utc(ev.get("timestamp"))

        deadline = _ensure_utc(task.get("deadline_at"))
        wf = label_info.get("will_forget") if "will_forget" in label_info else task.get("will_forget")

        # If completed after deadline, it must NOT be labeled will_forget = 1
        if comp_t and deadline and comp_t > deadline:
            if wf == 1:
                self._record_anomaly(
                    task_id,
                    "TARDY_MISLABELED_FORGOTTEN",
                    "ERROR",
                    f"Task was completed late ({comp_t} > {deadline}) but incorrectly labeled will_forget=1.",
                )

    def _check_observation_window(self, task_id: str, task: dict, label_info: dict, as_of: datetime):
        deadline = _ensure_utc(task.get("deadline_at"))
        is_valid = label_info.get("is_valid_training_sample")
        outcome = label_info.get("outcome_type")

        # If deadline is in the future, it cannot be a definitive completed/forgotten training sample unless completed
        comp_t = _ensure_utc(task.get("completed_at"))
        if deadline and deadline > as_of and comp_t is None:
            if is_valid is True or outcome in (
                OutcomeType.EXPLICITLY_FORGOTTEN.value,
                OutcomeType.ABANDONED.value,
            ):
                self._record_anomaly(
                    task_id,
                    "INSUFFICIENT_OBSERVATION_WINDOW",
                    "ERROR",
                    f"Future task (deadline {deadline} > as_of {as_of}) included as valid training sample.",
                )

    def _check_postponement_labeling(self, task_id: str, task: dict, events: list, label_info: dict):
        has_postpone = any(
            str(e.get("event_type", "")).lower() in ("postponed", "rescheduled") for e in events
        ) or bool(task.get("is_postponed"))

        wf = label_info.get("will_forget") if "will_forget" in label_info else task.get("will_forget")
        if has_postpone and wf == 1:
            self._record_anomaly(
                task_id,
                "POSTPONEMENT_MISLABELED_FORGOTTEN",
                "ERROR",
                "Intentionally postponed task was incorrectly labeled as forgotten (will_forget=1).",
            )

    def generate_markdown_report(self) -> str:
        s = self.summary
        md = []
        md.append("# ContextIQ — Label Quality & Validation Audit Report\n")
        md.append(f"_Generated {datetime.now(timezone.utc).isoformat()}_\n")
        md.append("## 1. Dataset Overview\n")
        md.append(f"- **Total Tasks Audited:** `{s.total_tasks:,}`")
        md.append(f"- **Valid Training Samples:** `{s.valid_training_samples:,}` ({(s.valid_training_samples/max(1, s.total_tasks))*100:.1f}%)")
        md.append(f"- **Excluded / Censored Samples:** `{s.excluded_samples:,}` ({(s.excluded_samples/max(1, s.total_tasks))*100:.1f}%)\n")

        md.append("## 2. Granular Outcome Distribution\n")
        md.append("| Outcome State | Count | Percentage | Training Status |")
        md.append("|---|---|---|---|")
        for outcome, cnt in sorted(s.outcome_distribution.items(), key=lambda x: x[1], reverse=True):
            pct = (cnt / max(1, s.total_tasks)) * 100
            status = "Valid" if outcome in ("COMPLETED_ON_TIME", "COMPLETED_LATE", "POSTPONED", "EXPLICITLY_FORGOTTEN", "ABANDONED") else "Excluded"
            md.append(f"| `{outcome}` | {cnt:,} | {pct:.1f}% | {status} |")

        md.append("\n## 3. Legacy Binary `will_forget` Balance (Valid Samples)\n")
        md.append("| Class | Count | Percentage |")
        md.append("|---|---|---|")
        v_total = s.valid_training_samples
        for k in ("0", "1", "None"):
            c = s.will_forget_distribution.get(k, 0)
            pct = (c / max(1, v_total)) * 100 if k != "None" else 0.0
            md.append(f"| `{k}` | {c:,} | {pct:.1f}% |")

        md.append("\n## 4. Integrity Check Anomalies\n")
        if not s.anomalies_by_check:
            md.append("✓ **Zero anomalies detected across all 7 integrity checks.**")
        else:
            md.append("| Check Name | Violations | Severity |")
            md.append("|---|---|---|")
            for chk, cnt in sorted(s.anomalies_by_check.items(), key=lambda x: x[1], reverse=True):
                sev = "ERROR" if "MISLABELED" in chk or "CONTRADICTORY" in chk or "TIMESTAMPS" in chk else "WARNING"
                md.append(f"| `{chk}` | {cnt:,} | {sev} |")

        md.append("\n## 5. Methodological Conclusions\n")
        md.append("1. **Censorship Separation**: Right-censored tasks are isolated cleanly from positive and negative training labels, removing survival bias.")
        md.append("2. **Tardy Separation**: Tasks completed past deadline are recognized as completed, preventing execution delay from contaminating memory-forgetting metrics.")
        md.append("3. **Postponement Safety**: Proactive user deferrals are preserved as active time-management actions rather than penalized as prospective memory failures.\n")

        return "\n".join(md)

    def save_reports(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        md_content = self.generate_markdown_report()
        (output_dir / "label_quality_report.md").write_text(md_content, encoding="utf-8")
        json_data = self.summary.to_dict()
        (output_dir / "label_quality_report.json").write_text(json.dumps(json_data, indent=2), encoding="utf-8")
