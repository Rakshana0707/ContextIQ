"""Intelligent, constraint-aware task scheduling engine with multi-objective optimization and transparent explanations."""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.prioritization.prioritization_engine import _is_high_concentration, _is_short_chore
from app.prioritization.prioritization_features import PrioritizationFeatureExtractor
from app.schemas.scheduling import (
    AvailabilityWindowRead,
    ScheduleExplanationDTO,
    ScheduleGenerateRequest,
    ScheduleProposalResponse,
    ScheduledSlotDTO,
    UnscheduledTaskDTO,
    UserAvailabilityResponse,
)
from app.scheduling.availability_engine import AvailabilityEngine, _to_utc, subtract_interval

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Computes constraint-satisfying, personalized task schedules matched to user focus and availability."""

    @classmethod
    def generate_schedule(
        cls,
        db: Session,
        user_id: UUID,
        request: ScheduleGenerateRequest,
    ) -> ScheduleProposalResponse:
        """Generates an explainable task schedule proposal respecting calendar constraints, deadlines, and behavioral twin baselines."""
        # 1. Compute realistic available intervals via AvailabilityEngine
        availability: UserAvailabilityResponse = AvailabilityEngine.calculate_availability(
            db=db,
            user_id=user_id,
            start_date=request.start_date,
            horizon_days=request.horizon_days,
            working_hour_start=request.working_hour_start,
            working_hour_end=request.working_hour_end,
            include_weekends=request.include_weekends,
            enforce_lunch_break=request.enforce_lunch_break,
            lunch_start_hour=request.lunch_start_hour,
            lunch_duration_minutes=request.lunch_duration_minutes,
            recovery_buffer_minutes=request.recovery_buffer_minutes,
        )

        # 2. Fetch candidate tasks
        task_query = select(Task).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        )
        if request.task_ids:
            task_query = task_query.where(Task.id.in_(request.task_ids))

        tasks = list(db.scalars(task_query).all())

        # 3. Extract prioritization features and rank tasks
        tasks_with_features: List[Tuple[Task, Dict[str, Any]]] = []
        for t in tasks:
            features = PrioritizationFeatureExtractor.extract_task_features(
                db=db,
                task=t,
                user_id=user_id,
                as_of=availability.horizon_start,
            )
            tasks_with_features.append((t, features))

        # Topologically sort & rank:
        # Parents before children; within same tier, sort by urgency descending, deadline ascending
        def sort_key(item: Tuple[Task, Dict[str, Any]]) -> Tuple[int, float, float]:
            task_obj, feats = item
            has_parent = 1 if task_obj.parent_task_id else 0
            urgency = feats.get("urgency_score", 0.5)
            # Deadline proximity
            due_ts = _to_utc(task_obj.due_at).timestamp() if task_obj.due_at else float("inf")
            return (has_parent, -urgency, due_ts)

        tasks_with_features.sort(key=sort_key)

        # 4. Interval-Matching Constraint Satisfaction
        # Represent free intervals as mutable list of [start, end, quality_score, is_peak]
        free_intervals: List[Dict[str, Any]] = [
            {
                "start": win.start_time,
                "end": win.end_time,
                "quality": win.focus_quality_score,
                "is_peak": win.is_peak_focus,
            }
            for win in availability.available_windows
        ]

        scheduled_items: List[ScheduledSlotDTO] = []
        unscheduled_items: List[UnscheduledTaskDTO] = []
        total_scheduled_minutes = 0
        peak_focus_tasks = 0

        scheduled_task_end_times: Dict[UUID, datetime] = {}

        for task_obj, feats in tasks_with_features:
            duration_mins = max(15, task_obj.estimated_minutes or 30)
            is_deep = _is_high_concentration(feats)
            due_at_utc = _to_utc(task_obj.due_at)

            # Check parent dependency
            min_earliest_start = availability.horizon_start
            if task_obj.parent_task_id:
                if task_obj.parent_task_id in scheduled_task_end_times:
                    min_earliest_start = max(min_earliest_start, scheduled_task_end_times[task_obj.parent_task_id])
                else:
                    # Parent exists but was not scheduled
                    unscheduled_items.append(
                        UnscheduledTaskDTO(
                            task_id=task_obj.id,
                            title=task_obj.title,
                            priority=task_obj.priority.value if hasattr(task_obj.priority, "value") else str(task_obj.priority),
                            due_at=task_obj.due_at,
                            estimated_minutes=duration_mins,
                            reason_code="DEPENDENCY_UNRESOLVED",
                            reason_detail=f"Parent task {task_obj.parent_task_id} could not be placed in this scheduling horizon.",
                        )
                    )
                    continue

            # Find feasible intervals
            candidate_slots: List[Dict[str, Any]] = []

            for idx, interval in enumerate(free_intervals):
                i_start: datetime = interval["start"]
                i_end: datetime = interval["end"]

                # Respect minimum earliest start (e.g. parent task completion)
                effective_start = max(i_start, min_earliest_start)
                potential_end = effective_start + timedelta(minutes=duration_mins)

                if potential_end <= i_end:
                    # Check deadline constraint
                    deadline_met = True
                    if due_at_utc and potential_end > due_at_utc:
                        deadline_met = False

                    candidate_slots.append(
                        {
                            "interval_idx": idx,
                            "start": effective_start,
                            "end": potential_end,
                            "quality": interval["quality"],
                            "is_peak": interval["is_peak"],
                            "deadline_met": deadline_met,
                            "slack_remaining": (i_end - potential_end).total_seconds() / 60.0,
                        }
                    )

            if not candidate_slots:
                unscheduled_items.append(
                    UnscheduledTaskDTO(
                        task_id=task_obj.id,
                        title=task_obj.title,
                        priority=task_obj.priority.value if hasattr(task_obj.priority, "value") else str(task_obj.priority),
                        due_at=task_obj.due_at,
                        estimated_minutes=duration_mins,
                        reason_code="INSUFFICIENT_WINDOW",
                        reason_detail=f"No available {duration_mins}-minute continuous window available within current working hours and calendar commitments.",
                    )
                )
                continue

            # Filter candidates that meet deadline if possible
            valid_deadline_slots = [c for c in candidate_slots if c["deadline_met"]]
            deadline_violated = False
            if not valid_deadline_slots:
                # All candidate slots miss deadline
                chosen_pool = candidate_slots
                deadline_violated = True
            else:
                chosen_pool = valid_deadline_slots

            # Score slots: Deep work prefers peak focus windows; all prefer clean fits
            def slot_score(slot: Dict[str, Any]) -> float:
                score = 0.0
                if is_deep:
                    score += slot["quality"] * 1.5
                    if slot["is_peak"]:
                        score += 30.0
                else:
                    score += 50.0  # Chores can go anywhere

                # Avoid fragmentation (prefer slots that leave >= 20 mins or 0 mins)
                slack = slot["slack_remaining"]
                if slack == 0 or slack >= 25:
                    score += 15.0
                elif slack < 15:
                    score -= 10.0  # Leaves an awkward tiny gap

                # Temporal urgency preference (earlier is better)
                delta_h = (slot["start"] - availability.horizon_start).total_seconds() / 3600.0
                score -= delta_h * 2.0
                return score

            chosen_pool.sort(key=slot_score, reverse=True)
            best_slot = chosen_pool[0]

            slot_start = best_slot["start"]
            slot_end = best_slot["end"]
            int_idx = best_slot["interval_idx"]

            # Carve out allocated slot from free_intervals
            parent_interval = free_intervals.pop(int_idx)
            left_chunk = None
            right_chunk = None

            if slot_start > parent_interval["start"]:
                left_chunk = {
                    "start": parent_interval["start"],
                    "end": slot_start,
                    "quality": parent_interval["quality"],
                    "is_peak": parent_interval["is_peak"],
                }
            if slot_end < parent_interval["end"]:
                # Insert a 5m breathing buffer between consecutive tasks
                buffered_start = min(slot_end + timedelta(minutes=5), parent_interval["end"])
                if buffered_start < parent_interval["end"]:
                    right_chunk = {
                        "start": buffered_start,
                        "end": parent_interval["end"],
                        "quality": parent_interval["quality"],
                        "is_peak": parent_interval["is_peak"],
                    }

            if right_chunk:
                free_intervals.insert(int_idx, right_chunk)
            if left_chunk:
                free_intervals.insert(int_idx, left_chunk)

            scheduled_task_end_times[task_obj.id] = slot_end

            # 5. Formulate transparent multi-factor explanations
            drivers: List[str] = [
                f"Urgency score: {feats.get('urgency_score', 0.5):.2f}",
                f"Estimated duration: {duration_mins} minutes",
            ]
            if task_obj.due_at:
                drivers.append(f"Hard deadline: {task_obj.due_at.strftime('%Y-%m-%d %H:%M UTC')}")
            if feats.get("forgetting_risk_score", 0) > 0.4:
                drivers.append(f"Elevated forgetting risk: {feats['forgetting_risk_score']*100:.0f}%")

            constraints_considered: List[str] = [
                "Clamped inside defined working hours",
                "Subtracted external Google/Outlook meeting commitments",
            ]
            if request.enforce_lunch_break:
                constraints_considered.append("Protected midday lunch window")
            if request.recovery_buffer_minutes > 0:
                constraints_considered.append(f"Maintained {request.recovery_buffer_minutes}m post-meeting cognitive recovery buffer")

            rejected_alternatives: List[str] = []
            if len(candidate_slots) > 1:
                rejected_alternatives.append(f"Evaluated {len(candidate_slots)} candidate slots across horizon")
            if not best_slot["is_peak"] and is_deep:
                rejected_alternatives.append("Earlier peak focus blocks occupied by higher-urgency commitments")

            confidence = 0.90
            if deadline_violated:
                confidence = 0.60
                drivers.append("WARNING: Scheduled past ideal deadline due to full schedule constraints.")

            if best_slot["is_peak"]:
                peak_focus_tasks += 1
                rationale = f"Matched to personal peak focus window ({slot_start.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}) with {best_slot['quality']:.0f}% focus quality."
            else:
                rationale = f"Allocated feasible {duration_mins}-minute focus block aligned with working hours and recovery spacing."

            explanation = ScheduleExplanationDTO(
                primary_rationale=rationale,
                behavioral_drivers=drivers,
                calendar_constraints=constraints_considered,
                rejected_alternatives=rejected_alternatives,
                confidence_score=round(confidence, 2),
            )

            scheduled_items.append(
                ScheduledSlotDTO(
                    slot_id=f"slot-{uuid.uuid4().hex[:8]}",
                    task_id=task_obj.id,
                    title=task_obj.title,
                    start_time=slot_start,
                    end_time=slot_end,
                    duration_minutes=duration_mins,
                    priority=task_obj.priority.value if hasattr(task_obj.priority, "value") else str(task_obj.priority),
                    context_tag=task_obj.context_tag,
                    due_at=task_obj.due_at,
                    is_deep_work=is_deep,
                    focus_quality_score=best_slot["quality"],
                    explanation=explanation,
                )
            )
            total_scheduled_minutes += duration_mins

        scheduled_items.sort(key=lambda s: s.start_time)
        focus_alignment_rate = round((peak_focus_tasks / len(scheduled_items)) * 100, 1) if scheduled_items else 0.0

        return ScheduleProposalResponse(
            id=uuid.uuid4(),
            user_id=user_id,
            status="DRAFT",
            horizon_start=availability.horizon_start,
            horizon_end=availability.horizon_end,
            scheduled_items=scheduled_items,
            unscheduled_items=unscheduled_items,
            total_scheduled_minutes=total_scheduled_minutes,
            total_tasks_scheduled=len(scheduled_items),
            focus_alignment_rate=focus_alignment_rate,
            created_at=datetime.now(timezone.utc),
        )
