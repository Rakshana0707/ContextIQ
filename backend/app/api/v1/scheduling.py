"""REST API endpoints for calendar-aware intelligent task scheduling engine."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.scheduling import (
    ScheduleApprovalRequest,
    ScheduleApprovalResponse,
    ScheduleGenerateRequest,
    ScheduleModifySlotRequest,
    ScheduleProposalResponse,
    ScheduleRejectRequest,
    UserAvailabilityResponse,
)
from app.services import scheduling_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


class SchedulePreviewRequest(BaseModel):
    schedule_id: uuid.UUID


@router.get("/availability", response_model=UserAvailabilityResponse)
def get_user_availability(
    start_date: Optional[datetime] = Query(None, description="Horizon start time"),
    horizon_days: int = Query(3, ge=1, le=14, description="Days to calculate availability"),
    working_hour_start: int = Query(9, ge=0, le=23, description="Earliest work hour"),
    working_hour_end: int = Query(17, ge=1, le=24, description="Latest work hour"),
    include_weekends: bool = Query(False, description="Whether to include weekends"),
    enforce_lunch_break: bool = Query(True, description="Whether to reserve midday lunch hour"),
    recovery_buffer_minutes: int = Query(15, ge=0, le=60, description="Post-meeting recovery buffer"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Calculate and return free working windows and busy calendar blackout periods."""
    return scheduling_service.get_user_availability(
        db=db,
        user_id=user_id,
        start_date=start_date,
        horizon_days=horizon_days,
        working_hour_start=working_hour_start,
        working_hour_end=working_hour_end,
        include_weekends=include_weekends,
        enforce_lunch_break=enforce_lunch_break,
        recovery_buffer_minutes=recovery_buffer_minutes,
    )


@router.post("/generate", response_model=ScheduleProposalResponse, status_code=status.HTTP_201_CREATED)
def generate_schedule_proposal(
    payload: ScheduleGenerateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Generate a constraint-aware, explainable schedule proposal draft."""
    try:
        return scheduling_service.generate_schedule(db=db, user_id=user_id, request=payload)
    except Exception as exc:
        logger.error("Failed to generate schedule: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate schedule proposal: {exc}",
        ) from exc


@router.post("/preview", response_model=ScheduleProposalResponse)
def preview_schedule_proposal(
    payload: SchedulePreviewRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieve an existing schedule proposal with full explanations for user preview."""
    try:
        return scheduling_service.preview_schedule(db=db, user_id=user_id, schedule_id=payload.schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/modify", response_model=ScheduleProposalResponse)
def modify_schedule_slot(
    payload: ScheduleModifySlotRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Adjust timing for a specific task slot inside a draft schedule proposal."""
    try:
        return scheduling_service.modify_schedule_slot(db=db, user_id=user_id, request=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/approve", response_model=ScheduleApprovalResponse)
def approve_schedule(
    payload: ScheduleApprovalRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Explicitly authorize committing approved schedule focus blocks to external calendar."""
    try:
        return scheduling_service.approve_schedule(db=db, user_id=user_id, request=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Schedule approval commit failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit schedule to calendar: {exc}",
        ) from exc


@router.post("/reject")
def reject_schedule(
    payload: ScheduleRejectRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Discard a proposed schedule draft without modifying external calendars."""
    success = scheduling_service.reject_schedule(
        db=db, user_id=user_id, schedule_id=payload.schedule_id, reason=payload.reason
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule proposal {payload.schedule_id} not found.",
        )
    return {
        "success": True,
        "schedule_id": payload.schedule_id,
        "status": "REJECTED",
        "message": "Schedule proposal successfully rejected.",
    }
