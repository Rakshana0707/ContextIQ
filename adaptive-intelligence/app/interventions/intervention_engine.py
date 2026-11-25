"""
Personalized Intervention Recommendation Engine (Phase 4.5).
Generates, ranks, deduplicates, and filters actionable interventions.
Enforces evidence sufficiency, contradiction elimination, and feedback personalization.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.interventions.intervention_catalog import CONTRADICTION_PAIRS, INTERVENTION_METADATA
from app.interventions.intervention_grounding import InterventionGroundingService
from app.schemas.intervention_schemas import (
    EstimatedEffort,
    InterventionCategory,
    InterventionLifecycleStatus,
    InterventionRead,
    InterventionType,
)


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class InterventionEngine:
    """Core computational engine for generating personalized, context-aware interventions."""

    @classmethod
    def generate_interventions(
        cls,
        user_id: uuid.UUID,
        tasks: Sequence[Any],
        focus_windows: Sequence[Any],
        profile_data: Optional[Dict[str, Any]],
        recent_interruptions: Sequence[Any],
        task_associations: Sequence[Any],
        current_hour: int,
        current_context_tag: Optional[str] = None,
        historical_feedback_stats: Optional[Dict[str, Dict[str, int]]] = None,
        recent_presented_types: Optional[Set[str]] = None,
        as_of: Optional[datetime] = None,
        max_interventions: int = 3,
    ) -> List[InterventionRead]:
        """
        Scans empirical context and generates ranked, non-contradictory interventions.
        Returns empty list if evidence is insufficient.
        """
        ref_time = _normalize_utc(as_of) or _normalize_utc(datetime.now(timezone.utc))
        fb_stats = historical_feedback_stats or {}
        presented_types = recent_presented_types or set()

        # Guard: Check for insufficient history / data
        # If user has 0 tasks, 0 sessions, and profile is missing or cold-start with no telemetry triggers:
        is_cold_start = False
        if profile_data:
            is_cold_start = profile_data.get("overall_pattern_status") == "INSUFFICIENT_EVIDENCE"
        elif not tasks and not recent_interruptions:
            return []

        # Find active focus window for current hour
        active_focus_window = None
        for fw in focus_windows:
            st = getattr(fw.start_time, "hour", 0)
            et = getattr(fw.end_time, "hour", 24)
            if st <= current_hour < et:
                active_focus_window = fw
                break

        # Compute telemetry signals
        bfi = 40.0
        hourly_int_freq = 1.0
        med_resumption_lag = 45.0
        if profile_data and "baselines" in profile_data:
            baselines = profile_data["baselines"]
            bfi = float(baselines.get("baseline_friction_index", 40.0))
            hourly_int_freq = float(baselines.get("hourly_interruption_frequency", 1.0))
            med_resumption_lag = float(baselines.get("typical_recovery_delay_seconds", 45.0))

        # Check recent interruptions count in last 2 hours
        two_hours_ago = ref_time - timedelta(hours=2)
        recent_int_count = sum(
            1 for i in recent_interruptions
            if _normalize_utc(getattr(i, "start_timestamp", None)) and _normalize_utc(getattr(i, "start_timestamp", None)) >= two_hours_ago
        )

        candidates: List[Dict[str, Any]] = []

        # ===================================================================
        # Rule Evaluation
        # ===================================================================

        # -------------------------------------------------------------------
        # A. Focus Interventions
        # -------------------------------------------------------------------
        # A.1 Protected Focus Session
        if active_focus_window and getattr(active_focus_window, "quality_score", 0.0) >= 58.0:
            deep_tasks = [
                t for t in tasks
                if getattr(t, "status", None) in {"PENDING", "IN_PROGRESS"}
                and (getattr(t, "estimated_minutes", 0) or 0) >= 40
            ]
            if deep_tasks:
                target_t = deep_tasks[0]
                ev = {
                    "focus_window_quality": round(float(getattr(active_focus_window, "quality_score", 75.0)), 1),
                    "window_start_hour": getattr(active_focus_window.start_time, "hour", 10),
                    "window_end_hour": getattr(active_focus_window.end_time, "hour", 12),
                    "task_duration": getattr(target_t, "estimated_minutes", 45),
                }
                candidates.append({
                    "type": InterventionType.SUGGEST_PROTECTED_FOCUS_SESSION.value,
                    "task_id": target_t.id,
                    "task_title": target_t.title,
                    "trigger": f"Active focus window (quality {ev['focus_window_quality']}) with deep task pending",
                    "evidence": ev,
                    "urgency_boost": 5.0,
                    "confidence": min(1.0, float(getattr(active_focus_window, "confidence_score", 0.85))),
                })

        # A.2 Reduce Application Switching
        if recent_int_count >= 5 or hourly_int_freq >= 6.0:
            ev = {
                "switch_frequency_hourly": round(max(float(recent_int_count), hourly_int_freq), 1),
            }
            candidates.append({
                "type": InterventionType.REDUCE_APPLICATION_SWITCHING.value,
                "task_id": None,
                "task_title": None,
                "trigger": f"Frequent window switching ({ev['switch_frequency_hourly']}/hr) exceeds stability threshold",
                "evidence": ev,
                "urgency_boost": 8.0,
                "confidence": 0.88,
            })

        # A.3 Select Suitable Focus Window
        if not active_focus_window and focus_windows:
            unfoc_deep_tasks = [
                t for t in tasks
                if getattr(t, "status", None) == "PENDING"
                and (getattr(t, "estimated_minutes", 0) or 0) >= 60
            ]
            if unfoc_deep_tasks:
                best_fw = max(focus_windows, key=lambda w: getattr(w, "quality_score", 0.0))
                target_t = unfoc_deep_tasks[0]
                ev = {
                    "recommended_hour": getattr(best_fw.start_time, "hour", 10),
                    "recommended_quality": round(float(getattr(best_fw, "quality_score", 80.0)), 1),
                    "task_duration": getattr(target_t, "estimated_minutes", 60),
                }
                candidates.append({
                    "type": InterventionType.SELECT_SUITABLE_FOCUS_WINDOW.value,
                    "task_id": target_t.id,
                    "task_title": target_t.title,
                    "trigger": f"Long-duration task pending outside peak focus window",
                    "evidence": ev,
                    "urgency_boost": 4.0,
                    "confidence": min(1.0, float(getattr(best_fw, "confidence_score", 0.80))),
                })

        # -------------------------------------------------------------------
        # B. Recovery Interventions
        # -------------------------------------------------------------------
        # B.1 Recovery Buffer
        if bfi >= 60.0 or recent_int_count >= 3:
            ev = {
                "behavioral_friction_index": round(bfi, 1),
                "consecutive_disruptions": max(3, recent_int_count),
            }
            candidates.append({
                "type": InterventionType.SUGGEST_RECOVERY_BUFFER.value,
                "task_id": None,
                "task_title": None,
                "trigger": f"BFI elevated ({ev['behavioral_friction_index']}) following {ev['consecutive_disruptions']} disruptions",
                "evidence": ev,
                "urgency_boost": 12.0,
                "confidence": 0.92,
            })

        # B.2 Resume Previous Task
        paused_tasks = [t for t in tasks if getattr(t, "status", None) in {"PAUSED", "IN_PROGRESS"}]
        if paused_tasks:
            t_paused = paused_tasks[0]
            created_utc = _normalize_utc(getattr(t_paused, "created_at", None)) or ref_time
            inactivity_mins = max(15.0, (ref_time - created_utc).total_seconds() / 60.0)
            ev = {
                "inactivity_minutes": round(inactivity_mins, 0),
            }
            candidates.append({
                "type": InterventionType.RESUME_PREVIOUS_TASK.value,
                "task_id": t_paused.id,
                "task_title": t_paused.title,
                "trigger": f"In-flight task paused for {ev['inactivity_minutes']} min",
                "evidence": ev,
                "urgency_boost": 7.0,
                "confidence": 0.85,
            })

        # B.3 Review Last Completed Step
        if med_resumption_lag >= 60.0:
            ev = {
                "resumption_lag_seconds": round(med_resumption_lag, 0),
            }
            candidates.append({
                "type": InterventionType.REVIEW_LAST_COMPLETED_STEP.value,
                "task_id": paused_tasks[0].id if paused_tasks else None,
                "task_title": paused_tasks[0].title if paused_tasks else None,
                "trigger": f"Extended recovery delay ({ev['resumption_lag_seconds']}s) warrants mental checkpointing",
                "evidence": ev,
                "urgency_boost": 4.0,
                "confidence": 0.80,
            })

        # -------------------------------------------------------------------
        # C. Task Interventions
        # -------------------------------------------------------------------
        # C.1 Break Large Task
        huge_tasks = [
            t for t in tasks
            if getattr(t, "status", None) == "PENDING"
            and (getattr(t, "estimated_minutes", 0) or 0) >= 90
        ]
        if huge_tasks:
            t_huge = huge_tasks[0]
            p90 = 60
            if profile_data and "focus_behavior" in profile_data:
                p90 = int(profile_data["focus_behavior"].get("p90_uninterrupted_minutes", {}).get("observed_value", 60) or 60)
            ev = {
                "estimated_minutes": getattr(t_huge, "estimated_minutes", 90),
                "typical_p90_focus_minutes": p90,
            }
            candidates.append({
                "type": InterventionType.BREAK_LARGE_TASK.value,
                "task_id": t_huge.id,
                "task_title": t_huge.title,
                "trigger": f"Task duration ({ev['estimated_minutes']} min) exceeds natural focus span ({p90} min)",
                "evidence": ev,
                "urgency_boost": 6.0,
                "confidence": 0.84,
            })

        # C.2 Review Approaching Deadline
        imminent_deadline_tasks = []
        for t in tasks:
            due_utc = _normalize_utc(getattr(t, "due_at", None))
            if due_utc and getattr(t, "status", None) == "PENDING":
                hours_left = (due_utc - ref_time).total_seconds() / 3600.0
                if 0.0 <= hours_left <= 6.0:
                    imminent_deadline_tasks.append((t, hours_left))

        if imminent_deadline_tasks:
            t_imm, h_left = imminent_deadline_tasks[0]
            ev = {
                "hours_to_deadline": round(h_left, 1),
            }
            candidates.append({
                "type": InterventionType.REVIEW_APPROACHING_DEADLINE.value,
                "task_id": t_imm.id,
                "task_title": t_imm.title,
                "trigger": f"Approaching deadline in {ev['hours_to_deadline']}h",
                "evidence": ev,
                "urgency_boost": 18.0,
                "confidence": 0.95,
            })

        # C.3 Postpone Low Priority Task
        urgent_tasks_count = sum(
            1 for t in tasks
            if getattr(t, "status", None) == "PENDING"
            and str(getattr(t, "priority", "")).upper() in {"URGENT", "HIGH"}
        )
        low_prio_tasks = [
            t for t in tasks
            if getattr(t, "status", None) == "PENDING"
            and str(getattr(t, "priority", "")).upper() == "LOW"
        ]
        if urgent_tasks_count >= 2 and low_prio_tasks:
            t_low = low_prio_tasks[0]
            ev = {
                "urgent_tasks_count": urgent_tasks_count,
            }
            candidates.append({
                "type": InterventionType.POSTPONE_LOW_PRIORITY_TASK.value,
                "task_id": t_low.id,
                "task_title": t_low.title,
                "trigger": f"High competition ({urgent_tasks_count} urgent tasks) warrants postponing low priority tasks",
                "evidence": ev,
                "urgency_boost": 3.0,
                "confidence": 0.78,
            })

        # -------------------------------------------------------------------
        # D. Contextual Interventions
        # -------------------------------------------------------------------
        # D.1 Location Exit / One More Thing Association
        if task_associations:
            assoc = task_associations[0]
            ev = {
                "associated_tasks_count": len(task_associations),
            }
            candidates.append({
                "type": InterventionType.COMPLETE_ASSOCIATED_TASKS_LOCATION_EXIT.value,
                "task_id": getattr(assoc, "antecedent_task_id", None),
                "task_title": getattr(assoc, "antecedent_task_title", "Anchor Task"),
                "trigger": f"Discovered task association with {ev['associated_tasks_count']} related items",
                "evidence": ev,
                "urgency_boost": 8.0,
                "confidence": min(1.0, float(getattr(assoc, "confidence", 0.75))),
            })

        # D.2 Batch Related Tasks
        category_counts: Dict[str, List[Any]] = {}
        for t in tasks:
            tag = getattr(t, "context_tag", None)
            if tag and getattr(t, "status", None) == "PENDING":
                category_counts.setdefault(tag, []).append(t)

        for cat, cat_tasks in category_counts.items():
            if len(cat_tasks) >= 3:
                ev = {
                    "batch_count": len(cat_tasks),
                    "category": cat,
                }
                candidates.append({
                    "type": InterventionType.BATCH_RELATED_TASKS.value,
                    "task_id": None,
                    "task_title": None,
                    "trigger": f"Batch opportunity: {ev['batch_count']} pending tasks in category '{cat}'",
                    "evidence": ev,
                    "urgency_boost": 5.0,
                    "confidence": 0.85,
                })
                break

        # -------------------------------------------------------------------
        # E. Workload Interventions
        # -------------------------------------------------------------------
        # E.1 Workload Exceeds Daily Focus Capacity
        total_pending_mins = sum(getattr(t, "estimated_minutes", 30) or 30 for t in tasks if getattr(t, "status", None) == "PENDING")
        total_pending_hours = total_pending_mins / 60.0
        daily_capacity_hours = 4.0
        if profile_data and "baselines" in profile_data:
            med_focus = profile_data["baselines"].get("median_focus_duration_minutes", 120.0)
            daily_capacity_hours = max(2.0, (med_focus * 2.0) / 60.0)

        if total_pending_hours >= (daily_capacity_hours * 1.5) and len(tasks) >= 4:
            ev = {
                "total_pending_hours": round(total_pending_hours, 1),
                "daily_focus_capacity_hours": round(daily_capacity_hours, 1),
            }
            candidates.append({
                "type": InterventionType.REDISTRIBUTE_TASKS.value,
                "task_id": None,
                "task_title": None,
                "trigger": f"Total pending workload ({ev['total_pending_hours']}h) exceeds daily capacity ({ev['daily_focus_capacity_hours']}h)",
                "evidence": ev,
                "urgency_boost": 9.0,
                "confidence": 0.88,
            })

        # E.2 Competing Deadlines
        pending_with_due = [
            (t, _normalize_utc(getattr(t, "due_at", None)))
            for t in tasks
            if getattr(t, "due_at", None) and getattr(t, "status", None) == "PENDING"
        ]
        if len(pending_with_due) >= 2:
            pending_with_due.sort(key=lambda x: x[1])
            t1, d1 = pending_with_due[0]
            t2, d2 = pending_with_due[1]
            diff_hours = abs((d2 - d1).total_seconds()) / 3600.0
            if diff_hours <= 4.0:
                ev = {
                    "competing_deadlines_count": 2,
                    "conflict_window_hours": 4,
                }
                candidates.append({
                    "type": InterventionType.REVIEW_COMPETING_DEADLINES.value,
                    "task_id": t1.id,
                    "task_title": t1.title,
                    "trigger": f"Overlapping deadlines within {ev['conflict_window_hours']}h",
                    "evidence": ev,
                    "urgency_boost": 11.0,
                    "confidence": 0.90,
                })

        # ===================================================================
        # Multi-Objective Scoring & Ranking
        # ===================================================================
        scored_candidates: List[Tuple[float, Dict[str, Any]]] = []

        for cand in candidates:
            itype = cand["type"]
            meta = INTERVENTION_METADATA.get(itype, {})
            base_rel = meta.get("base_relevance", 70.0)
            effort = meta.get("default_effort", EstimatedEffort.LOW.value)

            # Effort modifier
            effort_mod = 5.0 if effort == EstimatedEffort.LOW.value else (0.0 if effort == EstimatedEffort.MEDIUM.value else -10.0)

            # Feedback personalization modifier
            feedback_mod = 0.0
            if itype in fb_stats:
                stats = fb_stats[itype]
                acc = stats.get("ACCEPTED", stats.get("accepted", 0))
                dism = stats.get("DISMISSED", stats.get("dismissed", 0))
                tot = acc + dism + stats.get("DEFERRED", stats.get("deferred", 0))
                if tot >= 2:
                    acc_rate = acc / max(1, tot)
                    if acc_rate >= 0.60:
                        feedback_mod = 10.0  # Personalized boost
                    elif acc_rate <= 0.25:
                        feedback_mod = -8.0   # Personalized damping (non-fatal)

            # Repetition / fatigue damping
            fatigue_mod = -25.0 if itype in presented_types else 0.0

            final_score = base_rel + cand.get("urgency_boost", 0.0) + effort_mod + feedback_mod + fatigue_mod
            final_score = max(10.0, min(100.0, final_score))

            scored_candidates.append((final_score, cand))

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # ===================================================================
        # Contradiction Elimination & Deduplication
        # ===================================================================
        selected_interventions: List[InterventionRead] = []
        selected_types: Set[str] = set()

        for score, cand in scored_candidates:
            itype = cand["type"]
            meta = INTERVENTION_METADATA.get(itype, {})

            # 1. Contradiction check
            has_contradiction = False
            for pair in CONTRADICTION_PAIRS:
                if itype in pair:
                    conflicting = pair - {itype}
                    if any(ct in selected_types for ct in conflicting):
                        has_contradiction = True
                        break

            if has_contradiction:
                continue

            # 2. Avoid duplicate intervention types in the same batch
            if itype in selected_types:
                continue

            # 3. Intelligence Grounding
            title, message = InterventionGroundingService.generate_grounded_message(
                intervention_type=itype,
                supporting_evidence=cand["evidence"],
                task_title=cand["task_title"],
            )

            valid_dur_hours = meta.get("valid_duration_hours", 2)
            exp_time = ref_time + timedelta(hours=valid_dur_hours)

            selected_interventions.append(
                InterventionRead(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    associated_task_id=cand["task_id"],
                    intervention_type=itype,
                    intervention_category=meta.get("category", InterventionCategory.FOCUS.value),
                    title=title,
                    message=message,
                    trigger_condition=cand["trigger"],
                    supporting_evidence=cand["evidence"],
                    expected_outcome=meta.get("expected_outcome", "Improves cognitive workflow stability."),
                    estimated_effort=meta.get("default_effort", EstimatedEffort.LOW.value),
                    relevance_score=round(score, 1),
                    confidence=round(cand.get("confidence", 0.85), 2),
                    lifecycle_status=InterventionLifecycleStatus.GENERATED.value,
                    creation_timestamp=ref_time,
                    expiration_timestamp=exp_time,
                    deferred_until=None,
                    completed_at=None,
                    user_feedback_note=None,
                )
            )
            selected_types.add(itype)

            if len(selected_interventions) >= max_interventions:
                break

        return selected_interventions
