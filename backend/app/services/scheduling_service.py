"""Service orchestrating availability calculation, schedule proposal generation, previews, modifications, and calendar commits."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule_proposal import ScheduleProposal
from app.schemas.scheduling import (
    ScheduleApprovalRequest,
    ScheduleApprovalResponse,
    ScheduleGenerateRequest,
    ScheduleModifySlotRequest,
    ScheduleProposalResponse,
    ScheduledSlotDTO,
    UnscheduledTaskDTO,
    UserAvailabilityResponse,
)
from app.scheduling.availability_engine import AvailabilityEngine
from app.scheduling.calendar_writer import CalendarWriter
from app.scheduling.task_scheduler import TaskScheduler

logger = logging.getLogger(__name__)


def get_user_availability(
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
) -> UserAvailabilityResponse:
    """Calculates user's available time windows across all linked calendars and constraints."""
    return AvailabilityEngine.calculate_availability(
        db=db,
        user_id=user_id,
        start_date=start_date,
        horizon_days=horizon_days,
        working_hour_start=working_hour_start,
        working_hour_end=working_hour_end,
        include_weekends=include_weekends,
        enforce_lunch_break=enforce_lunch_break,
        lunch_start_hour=lunch_start_hour,
        lunch_duration_minutes=lunch_duration_minutes,
        recovery_buffer_minutes=recovery_buffer_minutes,
    )


def generate_schedule(
    db: Session,
    user_id: UUID,
    request: ScheduleGenerateRequest,
) -> ScheduleProposalResponse:
    """Generates an explainable task schedule proposal draft and stores it in the database."""
    proposal_resp = TaskScheduler.generate_schedule(db=db, user_id=user_id, request=request)

    # Persist draft proposal in database
    proposal_record = ScheduleProposal(
        id=proposal_resp.id,
        user_id=user_id,
        status="DRAFT",
        horizon_start=proposal_resp.horizon_start,
        horizon_end=proposal_resp.horizon_end,
        scheduled_items=[s.model_dump(mode="json") for s in proposal_resp.scheduled_items],
        unscheduled_items=[u.model_dump(mode="json") for u in proposal_resp.unscheduled_items],
        metadata_json={
            "total_scheduled_minutes": proposal_resp.total_scheduled_minutes,
            "total_tasks_scheduled": proposal_resp.total_tasks_scheduled,
            "focus_alignment_rate": proposal_resp.focus_alignment_rate,
        },
    )
    db.add(proposal_record)
    db.commit()
    db.refresh(proposal_record)
    return proposal_resp


def preview_schedule(
    db: Session,
    user_id: UUID,
    schedule_id: UUID,
) -> ScheduleProposalResponse:
    """Retrieves an existing schedule proposal with complete explainability traces."""
    stmt = select(ScheduleProposal).where(
        ScheduleProposal.id == schedule_id,
        ScheduleProposal.user_id == user_id,
    )
    proposal = db.scalars(stmt).first()
    if not proposal:
        raise ValueError(f"Schedule proposal {schedule_id} not found.")

    scheduled_slots = [ScheduledSlotDTO(**item) for item in proposal.scheduled_items]
    unscheduled = [UnscheduledTaskDTO(**item) for item in proposal.unscheduled_items]

    return ScheduleProposalResponse(
        id=proposal.id,
        user_id=proposal.user_id,
        status=proposal.status,
        horizon_start=proposal.horizon_start,
        horizon_end=proposal.horizon_end,
        scheduled_items=scheduled_slots,
        unscheduled_items=unscheduled,
        total_scheduled_minutes=proposal.metadata_json.get("total_scheduled_minutes", 0),
        total_tasks_scheduled=proposal.metadata_json.get("total_tasks_scheduled", len(scheduled_slots)),
        focus_alignment_rate=proposal.metadata_json.get("focus_alignment_rate", 0.0),
        created_at=proposal.created_at,
    )


def modify_schedule_slot(
    db: Session,
    user_id: UUID,
    request: ScheduleModifySlotRequest,
) -> ScheduleProposalResponse:
    """Modifies the timing of a single task slot within a draft schedule proposal."""
    stmt = select(ScheduleProposal).where(
        ScheduleProposal.id == request.schedule_id,
        ScheduleProposal.user_id == user_id,
    )
    proposal = db.scalars(stmt).first()
    if not proposal:
        raise ValueError(f"Schedule proposal {request.schedule_id} not found.")
    if proposal.status != "DRAFT":
        raise ValueError(f"Cannot modify schedule with status {proposal.status}. Only DRAFT schedules can be adjusted.")

    items = list(proposal.scheduled_items)
    target_slot = None
    for item in items:
        if item.get("slot_id") == request.slot_id:
            item["start_time"] = request.new_start_time.isoformat()
            item["end_time"] = request.new_end_time.isoformat()
            dur = int((request.new_end_time - request.new_start_time).total_seconds() / 60.0)
            item["duration_minutes"] = max(1, dur)
            target_slot = item
            break

    if not target_slot:
        raise ValueError(f"Slot {request.slot_id} not found in schedule {request.schedule_id}.")

    proposal.scheduled_items = items
    proposal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)

    return preview_schedule(db, user_id, request.schedule_id)


def approve_schedule(
    db: Session,
    user_id: UUID,
    request: ScheduleApprovalRequest,
) -> ScheduleApprovalResponse:
    """Commits an approved schedule proposal to the user's external calendar."""
    stmt = select(ScheduleProposal).where(
        ScheduleProposal.id == request.schedule_id,
        ScheduleProposal.user_id == user_id,
    )
    proposal = db.scalars(stmt).first()
    if not proposal:
        raise ValueError(f"Schedule proposal {request.schedule_id} not found.")
    if proposal.status == "REJECTED":
        raise ValueError("Cannot approve a schedule proposal that has been rejected.")

    return CalendarWriter.commit_approved_schedule(
        db=db,
        user_id=user_id,
        proposal=proposal,
        request=request,
    )


def reject_schedule(
    db: Session,
    user_id: UUID,
    schedule_id: UUID,
    reason: Optional[str] = None,
) -> bool:
    """Discards a proposed task schedule without modifying external calendars."""
    stmt = select(ScheduleProposal).where(
        ScheduleProposal.id == schedule_id,
        ScheduleProposal.user_id == user_id,
    )
    proposal = db.scalars(stmt).first()
    if not proposal:
        return False

    proposal.status = "REJECTED"
    if reason:
        meta = dict(proposal.metadata_json or {})
        meta["rejection_reason"] = reason
        proposal.metadata_json = meta

    proposal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True
