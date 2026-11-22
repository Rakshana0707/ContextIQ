import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.context_session import (
    ContextSessionCorrectionRequest,
    ContextSessionListResponse,
    ContextSessionRead,
    ContextSessionTimelineResponse,
    SessionReconstructionTriggerRequest,
    SessionTimelineSegment,
)
from app.services import session_reconstruction_engine

router = APIRouter(prefix="/context", tags=["context-sessions"])


@router.get("/sessions", response_model=ContextSessionListResponse)
def list_context_sessions(
    task_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    quality_tier: Optional[str] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves paginated, filtered work sessions reconstructed from telemetry."""
    items, total = session_reconstruction_engine.query_context_sessions(
        db=db,
        user_id=user_id,
        task_id=task_id,
        status=status_filter,
        quality_tier=quality_tier,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return ContextSessionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/sessions/reconstruct", status_code=status.HTTP_200_OK)
def trigger_session_reconstruction(
    payload: Optional[SessionReconstructionTriggerRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Triggers incremental or full session reconstruction over desktop telemetry,
    task events, and interruptions.
    """
    opts = payload or SessionReconstructionTriggerRequest()
    count = session_reconstruction_engine.reconstruct_sessions_for_user(
        db=db,
        user_id=user_id,
        lookback_hours=opts.lookback_hours,
        force_full_rebuild=opts.force_full_rebuild,
    )
    return {
        "status": "ok",
        "user_id": str(user_id),
        "sessions_reconstructed": count,
        "incremental": not opts.force_full_rebuild,
    }


@router.get("/sessions/{session_id}", response_model=ContextSessionRead)
def get_context_session_detail(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Fetches full details of a specific reconstructed session."""
    session_obj = session_reconstruction_engine.get_context_session_by_id(
        db=db, user_id=user_id, session_id=session_id
    )
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context session not found",
        )
    return session_obj


@router.get("/sessions/{session_id}/timeline", response_model=ContextSessionTimelineResponse)
def get_context_session_timeline(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves chronological timeline segments and metrics for a session."""
    session_obj = session_reconstruction_engine.get_context_session_by_id(
        db=db, user_id=user_id, session_id=session_id
    )
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context session not found",
        )

    duration = 0.0
    if session_obj.ended_at and session_obj.started_at:
        duration = max(0.0, (session_obj.ended_at - session_obj.started_at).total_seconds())

    # Parse timeline segments
    raw_segments = session_obj.timeline or []
    segments = []
    for raw in raw_segments:
        try:
            segments.append(
                SessionTimelineSegment(
                    segment_id=raw.get("segment_id", str(uuid.uuid4())),
                    segment_type=raw.get("segment_type", "FOCUS"),
                    started_at=datetime.fromisoformat(raw["started_at"]),
                    ended_at=datetime.fromisoformat(raw["ended_at"]) if raw.get("ended_at") else None,
                    duration_seconds=float(raw.get("duration_seconds", 0.0)),
                    application_identifier=raw.get("application_identifier"),
                    task_id=uuid.UUID(raw["task_id"]) if raw.get("task_id") else None,
                    notes=raw.get("notes"),
                )
            )
        except Exception:
            continue

    return ContextSessionTimelineResponse(
        session_id=session_obj.id,
        user_id=session_obj.user_id,
        started_at=session_obj.started_at,
        ended_at=session_obj.ended_at,
        total_duration_seconds=round(duration, 2),
        focused_time_seconds=session_obj.focused_time_seconds,
        interruption_time_seconds=session_obj.interruption_time_seconds,
        idle_time_seconds=session_obj.idle_time_seconds,
        primary_application=session_obj.primary_application,
        task_id=session_obj.task_id,
        timeline=segments,
    )


@router.post("/sessions/{session_id}/correct", response_model=ContextSessionRead)
def correct_context_session_endpoint(
    session_id: uuid.UUID,
    payload: ContextSessionCorrectionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Allows user to manually correct or assign task context to a reconstructed session."""
    try:
        return session_reconstruction_engine.correct_context_session(
            db=db,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
