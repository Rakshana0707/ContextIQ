"""
Adaptive Task Prioritization & Personalized Scheduling Engine (Phase 4.4).
Combines task urgency, forgetting risk, personal suitability, context compatibility,
and scheduling feasibility into an explainable, deterministic ranking queue.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.schemas.task_ranking import (
    RankedTaskItem,
    RankingPreset,
    RankingWeightConfig,
    RecommendedFocusWindow,
    ScoreBreakdown,
)


def _is_high_concentration(task_features: Dict[str, Any]) -> bool:
    tag = (task_features.get("context_tag") or "").lower()
    title = (task_features.get("title") or "").lower()
    dur = task_features.get("estimated_minutes", 30)

    deep_tags = {"programming", "coding", "writing", "analysis", "deep_work", "design", "study", "research"}
    if any(dt in tag for dt in deep_tags) or any(dt in title for dt in deep_tags):
        return True
    return dur >= 45


def _is_short_chore(task_features: Dict[str, Any]) -> bool:
    tag = (task_features.get("context_tag") or "").lower()
    title = (task_features.get("title") or "").lower()
    dur = task_features.get("estimated_minutes", 30)

    chore_tags = {"admin", "chore", "errand", "email", "routine", "quick", "call", "slack"}
    if any(ct in tag for ct in chore_tags) or any(ct in title for ct in chore_tags):
        return True
    return dur <= 20


class PrioritizationEngine:
    """Core multi-objective scoring and ranking engine."""

    @classmethod
    def rank_tasks(
        cls,
        tasks_features: List[Dict[str, Any]],
        focus_windows: List[Any],
        current_hour: int,
        current_context_tag: Optional[str] = None,
        weights: Optional[RankingWeightConfig] = None,
        preset: Optional[RankingPreset | str] = None,
        include_blocked: bool = True,
        pending_task_ids: Optional[set] = None,
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> List[RankedTaskItem]:
        """
        Ranks all candidate tasks, producing deterministic scores and explanations.
        Never modifies task schedules silently.
        """
        w_config = (
            weights.normalized()
            if weights
            else RankingWeightConfig.for_preset(preset or RankingPreset.BALANCED).normalized()
        )

        pending_ids = pending_task_ids or set()

        # Find if current_hour is inside an active focus window
        active_window = None
        for fw in focus_windows:
            start_h = getattr(fw.start_time, "hour", 0)
            end_h = getattr(fw.end_time, "hour", 24)
            if start_h <= current_hour < end_h:
                active_window = fw
                break

        # Check if current_hour is a known fragmented period
        is_fragmented = False
        if profile_data and "baselines" in profile_data:
            hourly_int = profile_data["baselines"].get("hourly_interruption_frequency", 1.0)
            if hourly_int >= 3.0:
                is_fragmented = True

        ranked_items: List[RankedTaskItem] = []

        for tf in tasks_features:
            task_id = tf["task_id"]
            u_score = tf["urgency_score"]
            f_score = tf["forgetting_risk_score"]
            est_mins = tf["estimated_minutes"]
            rec_buf = tf["recovery_buffer_minutes"]
            tag = tf.get("context_tag")

            # -------------------------------------------------------------
            # 1. Personal Suitability P(t)
            # -------------------------------------------------------------
            is_deep = _is_high_concentration(tf)
            is_chore = _is_short_chore(tf)

            if active_window and getattr(active_window, "quality_score", 0.0) >= 58.0:
                # In verified high-quality focus window
                if is_deep:
                    win_q = getattr(active_window, "quality_score", 70.0)
                    p_score = min(1.0, 0.85 + 0.15 * (win_q / 100.0))
                    # Category boost if task category matches focus window category
                    if getattr(active_window, "task_category", None) and getattr(active_window, "task_category", None) == tag:
                        p_score = min(1.0, p_score + 0.05)
                elif is_chore:
                    # Do not waste prime focus window on small administrative chores
                    p_score = 0.35
                else:
                    p_score = 0.65
            elif is_fragmented:
                # In fragmented / high disruption period
                if is_chore:
                    p_score = 0.90  # Ideal quick win between disruptions
                elif is_deep:
                    p_score = 0.25  # Avoid fracture of deep work
                else:
                    p_score = 0.50
            else:
                # Neutral working period
                p_score = 0.55
                if profile_data and "task_completion" in profile_data:
                    cat_rates = profile_data["task_completion"].get("task_completion_rate", {}).get("observed_value", {})
                    if isinstance(cat_rates, dict) and tag in cat_rates:
                        p_score = min(0.85, max(0.35, float(cat_rates[tag])))

            # -------------------------------------------------------------
            # 2. Context Compatibility C(t)
            # -------------------------------------------------------------
            if current_context_tag and tag:
                if current_context_tag.strip().lower() == tag.strip().lower():
                    c_score = 0.90
                else:
                    # Context-switch penalty
                    c_score = 0.35
            else:
                c_score = 0.55  # Neutral when no active desktop context is reported

            # -------------------------------------------------------------
            # 3. Scheduling Feasibility S(t) & Constraints
            # -------------------------------------------------------------
            constraints: List[str] = []
            is_blocked = False
            blocked_by = tf.get("parent_task_id")

            if blocked_by and blocked_by in pending_ids:
                is_blocked = True
                s_score = 0.0
                constraints.append("Blocked: Parent task is pending completion")
            else:
                total_block = est_mins + rec_buf
                if active_window:
                    end_h = getattr(active_window.end_time, "hour", 24)
                    mins_remaining = max(15, (end_h - current_hour) * 60)
                    if total_block <= mins_remaining:
                        s_score = 0.95
                        constraints.append(f"Fits within active focus window ({total_block} min needed, {mins_remaining} min available)")
                    else:
                        s_score = 0.50
                        constraints.append(f"Exceeds remaining focus window duration ({total_block} min needed vs {mins_remaining} min left)")
                else:
                    s_score = 0.75
                    constraints.append(f"Allocated {rec_buf} min recovery buffer")

            # -------------------------------------------------------------
            # 4. Multi-Objective Composite Score
            # -------------------------------------------------------------
            # Urgent deadlines (< 4h) strongly escalate overall urgency
            if tf.get("hours_to_deadline") is not None and tf["hours_to_deadline"] <= 4.0:
                # Critical deadline escalation
                raw_composite = (
                    0.55 * u_score
                    + 0.15 * f_score
                    + 0.15 * p_score
                    + 0.05 * c_score
                    + 0.10 * s_score
                )
            else:
                raw_composite = (
                    w_config.urgency_weight * u_score
                    + w_config.forgetting_risk_weight * f_score
                    + w_config.personal_suitability_weight * p_score
                    + w_config.context_compatibility_weight * c_score
                    + w_config.scheduling_feasibility_weight * s_score
                )

            composite_score = round(max(0.0, min(100.0, raw_composite * 100.0)), 1)
            if is_blocked:
                # Heavily discount blocked tasks so they do not outrank actionable work
                composite_score = round(composite_score * 0.25, 1)

            # -------------------------------------------------------------
            # 5. Primary Driver & Grounded Explanations
            # -------------------------------------------------------------
            driver, explanation = cls._synthesize_explanation(
                tf=tf,
                u_score=u_score,
                f_score=f_score,
                p_score=p_score,
                c_score=c_score,
                s_score=s_score,
                is_deep=is_deep,
                is_chore=is_chore,
                active_window=active_window,
                is_fragmented=is_fragmented,
                is_blocked=is_blocked,
            )

            # -------------------------------------------------------------
            # 6. Recommended Focus Window
            # -------------------------------------------------------------
            rec_window = None
            if active_window and is_deep and not is_blocked:
                rec_window = RecommendedFocusWindow(
                    start_time=f"{active_window.start_time.hour:02d}:00",
                    end_time=f"{active_window.end_time.hour:02d}:00",
                    quality_score=getattr(active_window, "quality_score", 75.0),
                    task_category=getattr(active_window, "task_category", tag),
                    reason="Optimal concentration match with current active focus window",
                )
            elif focus_windows and is_deep and not is_blocked:
                # Suggest highest-quality upcoming window
                best_w = max(focus_windows, key=lambda w: getattr(w, "quality_score", 0.0))
                rec_window = RecommendedFocusWindow(
                    start_time=f"{best_w.start_time.hour:02d}:00",
                    end_time=f"{best_w.end_time.hour:02d}:00",
                    quality_score=getattr(best_w, "quality_score", 75.0),
                    task_category=getattr(best_w, "task_category", tag),
                    reason=f"Recommended for upcoming high-quality focus window (Score {getattr(best_w, 'quality_score', 0):.0f})",
                )

            # Data sufficiency classification
            data_suff = "INSUFFICIENT_EVIDENCE" if tf.get("is_cold_start", False) else "ESTABLISHED"

            ranked_items.append(
                RankedTaskItem(
                    task_id=task_id,
                    title=tf["title"],
                    context_tag=tag,
                    priority=tf["priority"],
                    status=tf["status"],
                    due_at=tf["due_at"],
                    estimated_minutes=est_mins,
                    recovery_buffer_minutes=rec_buf,
                    rank=0,  # Will be assigned after sorting
                    composite_score=composite_score,
                    primary_driver=driver,
                    score_breakdown=ScoreBreakdown(
                        urgency_score=round(u_score, 3),
                        forgetting_risk_score=round(f_score, 3),
                        personal_suitability_score=round(p_score, 3),
                        context_compatibility_score=round(c_score, 3),
                        scheduling_feasibility_score=round(s_score, 3),
                    ),
                    grounded_explanation=explanation,
                    recommended_focus_window=rec_window,
                    constraints_applied=constraints,
                    is_blocked=is_blocked,
                    blocked_by_task_id=blocked_by if is_blocked else None,
                    data_sufficiency=data_suff,
                )
            )

        if not include_blocked:
            ranked_items = [it for it in ranked_items if not it.is_blocked]

        # Sort descending by composite score, putting non-blocked first
        ranked_items.sort(key=lambda it: (not it.is_blocked, it.composite_score), reverse=True)

        # Assign final 1-based ranks
        for idx, item in enumerate(ranked_items):
            item.rank = idx + 1

        return ranked_items

    @classmethod
    def _synthesize_explanation(
        cls,
        tf: Dict[str, Any],
        u_score: float,
        f_score: float,
        p_score: float,
        c_score: float,
        s_score: float,
        is_deep: bool,
        is_chore: bool,
        active_window: Optional[Any],
        is_fragmented: bool,
        is_blocked: bool,
    ) -> Tuple[str, str]:
        """Produces deterministic, grounded natural-language explanations."""
        if is_blocked:
            return (
                "BLOCKED_DEPENDENCY",
                f"Task is currently blocked by pending parent task dependency. Scheduled once parent is resolved.",
            )

        hours_to_due = tf.get("hours_to_deadline")
        if tf.get("is_overdue", False):
            return (
                "CRITICAL_DEADLINE",
                f"Task is overdue! Explicit priority {tf['priority']} escalates urgency score to {u_score:.2f}.",
            )

        if hours_to_due is not None and hours_to_due <= 4.0:
            return (
                "CRITICAL_DEADLINE",
                f"Approaching deadline in {hours_to_due:.1f} hours overrides standard scheduling preferences (urgency {u_score:.2f}).",
            )

        if active_window and is_deep:
            win_q = getattr(active_window, "quality_score", 75.0)
            return (
                "FOCUS_WINDOW_MATCH",
                f"High-concentration task matches active focus window (quality {win_q:.0f}/100). Personal suitability scored {p_score:.2f}.",
            )

        if is_fragmented and is_chore:
            return (
                "QUICK_WIN_ADMIN",
                f"Short chore ({tf['estimated_minutes']} min) prioritized for active fragmented period without risking deep concentration fracture.",
            )

        if f_score >= 0.65:
            return (
                "FORGETTING_RISK_SHIELD",
                f"Elevated forgetting risk ({tf.get('forgetting_prob', 0):.0%}) and inactivity ({tf.get('age_days', 0):.0f} days old) warrant timely execution.",
            )

        if c_score >= 0.85:
            return (
                "CONTEXT_ALIGNMENT",
                f"Task context tag matches current work domain, eliminating context-switching micro-delays.",
            )

        return (
            "BALANCED_PRIORITY",
            f"Balanced priority: urgency {u_score:.2f}, forgetting risk {f_score:.2f}, and feasibility {s_score:.2f}.",
        )
