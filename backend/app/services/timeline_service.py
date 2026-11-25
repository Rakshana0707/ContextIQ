"""Unified Timeline and Cross-Device Synchronization Service (Phase 5.7)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detected_interruption import DetectedInterruption
from app.models.external_calendar_event import ExternalCalendarEvent
from app.models.raw_telemetry_event import RawTelemetryEvent
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.user_device import UserDevice
from app.schemas.timeline import (
    CrossDeviceSessionRead,
    CrossDeviceSyncRequest,
    CrossDeviceSyncResponse,
    UnifiedTimelineEventDTO,
)
from app.services.device_service import DeviceService
from app.services.session_reconstruction_engine import SessionReconstructionEngine

logger = logging.getLogger(__name__)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TimelineService:
    @classmethod
    def sync_device_events(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: CrossDeviceSyncRequest,
    ) -> CrossDeviceSyncResponse:
        """
        Ingests a batch of cross-device events with idempotency,
        clock-skew drift estimation, and device authorization validation.
        """
        # 1. Enforce device authorization & touch last_seen
        device = DeviceService.verify_device_active(db, user_id, request.device_id)

        now_utc = datetime.now(timezone.utc)
        client_ts_utc = _to_utc(request.client_timestamp) or now_utc
        clock_skew = (now_utc - client_ts_utc).total_seconds()

        received = len(request.events)
        ingested = 0
        dropped_duplicates = 0

        # Query existing event IDs in this batch to enforce idempotency
        batch_event_ids = [str(ev.get("event_id")) for ev in request.events if ev.get("event_id")]
        existing_ids: Set[str] = set()
        if batch_event_ids:
            check_stmt = select(RawTelemetryEvent.event_id).where(
                RawTelemetryEvent.event_id.in_(batch_event_ids)
            )
            existing_ids = set(db.scalars(check_stmt).all())

        new_telemetry: List[RawTelemetryEvent] = []

        for item in request.events:
            raw_eid = item.get("event_id")
            if not raw_eid:
                raw_eid = f"ev_{uuid.uuid4().hex[:16]}"
            eid = str(raw_eid)

            if eid in existing_ids:
                dropped_duplicates += 1
                continue

            existing_ids.add(eid)

            # Occurrence timestamp normalization
            raw_ts = item.get("event_timestamp") or item.get("occurred_at")
            if isinstance(raw_ts, str):
                try:
                    event_dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except Exception:
                    event_dt = now_utc
            elif isinstance(raw_ts, datetime):
                event_dt = raw_ts
            else:
                event_dt = now_utc

            event_dt = _to_utc(event_dt)

            ev_obj = RawTelemetryEvent(
                event_id=eid,
                user_id=user_id,
                device_id=request.device_id,
                event_type=item.get("event_type", "APP_FOCUS"),
                event_timestamp=event_dt,
                ingestion_timestamp=now_utc,
                source=item.get("source", f"agent_{device.platform.lower()}"),
                schema_version=item.get("schema_version", "1.0.0"),
                application_identifier=item.get("application_identifier") or item.get("app_id"),
                payload={
                    **item.get("payload", {}),
                    "client_clock_skew_seconds": clock_skew,
                    "device_type": device.device_type,
                    "platform": device.platform,
                },
            )
            new_telemetry.append(ev_obj)
            ingested += 1

        if new_telemetry:
            db.add_all(new_telemetry)

        device.last_seen_timestamp = now_utc
        device.connection_status = "ONLINE"
        db.commit()

        return CrossDeviceSyncResponse(
            received=received,
            ingested=ingested,
            dropped_duplicates=dropped_duplicates,
            estimated_clock_skew_seconds=round(clock_skew, 2),
            sync_status="SYNCED",
            processed_at=now_utc,
        )

    @classmethod
    def get_unified_timeline(
        cls,
        db: Session,
        user_id: uuid.UUID,
        device_id: Optional[str] = None,
        device_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        task_id: Optional[uuid.UUID] = None,
        application: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UnifiedTimelineEventDTO]:
        """
        Retrieves a chronologically unified event stream synthesized from
        telemetry (desktop/mobile), tasks, interruptions, and external calendars.
        """
        # Fetch device map for friendly naming
        dev_stmt = select(UserDevice).where(UserDevice.user_id == user_id)
        devices = {d.device_id: d for d in db.scalars(dev_stmt).all()}

        events: List[UnifiedTimelineEventDTO] = []

        # 1. Raw Telemetry Events
        t_stmt = select(RawTelemetryEvent).where(RawTelemetryEvent.user_id == user_id)
        if device_id:
            t_stmt = t_stmt.where(RawTelemetryEvent.device_id == device_id)
        if start_time:
            t_stmt = t_stmt.where(RawTelemetryEvent.event_timestamp >= _to_utc(start_time))
        if end_time:
            t_stmt = t_stmt.where(RawTelemetryEvent.event_timestamp <= _to_utc(end_time))
        if application:
            t_stmt = t_stmt.where(RawTelemetryEvent.application_identifier.ilike(f"%{application}%"))
        if event_type:
            t_stmt = t_stmt.where(RawTelemetryEvent.event_type == event_type)

        raw_telemetry = list(db.scalars(t_stmt.order_by(RawTelemetryEvent.event_timestamp.desc()).limit(limit * 2)).all())

        for rt in raw_telemetry:
            dev = devices.get(rt.device_id or "")
            d_type = dev.device_type if dev else rt.payload.get("device_type", "DESKTOP")
            if device_type and d_type.upper() != device_type.upper():
                continue

            events.append(
                UnifiedTimelineEventDTO(
                    event_id=rt.event_id,
                    source=rt.source,
                    device_id=rt.device_id,
                    device_name=dev.device_name if dev else (f"Device ({rt.device_id[:6]})" if rt.device_id else None),
                    device_type=d_type,
                    platform=dev.platform if dev else rt.payload.get("platform", "WINDOWS"),
                    event_type=rt.event_type,
                    occurred_at=_to_utc(rt.event_timestamp),
                    ingested_at=_to_utc(rt.ingestion_timestamp),
                    timezone_offset_minutes=0,
                    clock_skew_seconds=float(rt.payload.get("client_clock_skew_seconds", 0.0)),
                    application_identifier=rt.application_identifier,
                    payload=rt.payload or {},
                )
            )

        # 2. Task Events
        if not device_id:
            tk_stmt = (
                select(TaskEvent)
                .join(Task, TaskEvent.task_id == Task.id)
                .where(Task.user_id == user_id)
            )
            if task_id:
                tk_stmt = tk_stmt.where(TaskEvent.task_id == task_id)
            if start_time:
                tk_stmt = tk_stmt.where(TaskEvent.occurred_at >= _to_utc(start_time))
            if end_time:
                tk_stmt = tk_stmt.where(TaskEvent.occurred_at <= _to_utc(end_time))

            for tev in db.scalars(tk_stmt.order_by(TaskEvent.occurred_at.desc()).limit(limit)).all():
                events.append(
                    UnifiedTimelineEventDTO(
                        event_id=f"task-ev-{tev.id}",
                        source="web_nextjs",
                        device_type="WEB",
                        platform="WEB",
                        event_type=f"TASK_{tev.event_type.value}",
                        occurred_at=_to_utc(tev.occurred_at),
                        ingested_at=_to_utc(tev.occurred_at),
                        task_id=tev.task_id,
                        payload=tev.payload or {},
                    )
                )

        # 3. External Calendar Events
        if not device_id:
            cal_stmt = select(ExternalCalendarEvent).where(
                ExternalCalendarEvent.user_id == user_id,
                ExternalCalendarEvent.status != "CANCELLED",
            )
            if start_time:
                cal_stmt = cal_stmt.where(ExternalCalendarEvent.end_time >= _to_utc(start_time))
            if end_time:
                cal_stmt = cal_stmt.where(ExternalCalendarEvent.start_time <= _to_utc(end_time))

            for cal_ev in db.scalars(cal_stmt.order_by(ExternalCalendarEvent.start_time.desc()).limit(20)).all():
                events.append(
                    UnifiedTimelineEventDTO(
                        event_id=f"cal-{cal_ev.id}",
                        source=f"calendar_{getattr(cal_ev, 'provider', 'cloud')}",
                        device_type="CALENDAR",
                        platform="CLOUD",
                        event_type="CALENDAR_COMMITMENT",
                        occurred_at=_to_utc(cal_ev.start_time),
                        ingested_at=_to_utc(cal_ev.created_at),
                        original_event_id=cal_ev.external_event_id,
                        duration_seconds=(cal_ev.end_time - cal_ev.start_time).total_seconds(),
                        payload={
                            "title": cal_ev.title,
                            "transparency": cal_ev.transparency,
                            "is_all_day": cal_ev.is_all_day,
                        },
                    )
                )

        # Chronological sorting: newest first for timeline view
        events.sort(key=lambda x: x.occurred_at, reverse=True)
        return events[offset : offset + limit]

    @classmethod
    def get_cross_device_sessions(
        cls,
        db: Session,
        user_id: uuid.UUID,
        lookback_hours: int = 24,
    ) -> List[CrossDeviceSessionRead]:
        """
        Executes unified cross-device session reconstruction.
        Stitches events across desktop, mobile, and web into cohesive sessions,
        computing device breakdown and cross-device interruption metrics.
        """
        engine = SessionReconstructionEngine()

        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        telemetry_events = list(
            db.scalars(
                select(RawTelemetryEvent)
                .where(
                    RawTelemetryEvent.user_id == user_id,
                    RawTelemetryEvent.event_timestamp >= since,
                )
                .order_by(RawTelemetryEvent.event_timestamp.asc())
            ).all()
        )

        task_events = list(
            db.scalars(
                select(TaskEvent)
                .join(Task, TaskEvent.task_id == Task.id)
                .where(
                    Task.user_id == user_id,
                    TaskEvent.occurred_at >= since,
                )
                .order_by(TaskEvent.occurred_at.asc())
            ).all()
        )

        detected_interruptions = list(
            db.scalars(
                select(DetectedInterruption)
                .where(
                    DetectedInterruption.user_id == user_id,
                    DetectedInterruption.start_timestamp >= since,
                )
                .order_by(DetectedInterruption.start_timestamp.asc())
            ).all()
        )

        # Unified merge and sort
        unified_events = engine.merge_and_sort_events(
            telemetry_events=telemetry_events,
            task_events=task_events,
            detected_interruptions=detected_interruptions,
            manual_interruptions=[],
        )

        reconstructed = engine.reconstruct(
            unified_events=unified_events,
            user_id=user_id,
        )

        results: List[CrossDeviceSessionRead] = []
        for s in reconstructed:
            # Calculate device breakdown and transitions
            time_breakdown: Dict[str, float] = {}
            device_transitions = 0
            last_device_type: Optional[str] = None
            cross_device_int_sec = 0.0

            tl = s.get("timeline", [])
            for seg in tl:
                d_type = seg.get("device_type", "DESKTOP")
                dur = float(seg.get("duration_seconds") or seg.get("duration") or 0.0)
                time_breakdown[d_type] = time_breakdown.get(d_type, 0.0) + dur

                if last_device_type and last_device_type != d_type:
                    device_transitions += 1
                    if d_type == "MOBILE" and last_device_type == "DESKTOP":
                        cross_device_int_sec += dur

                last_device_type = d_type

            # Primary device type
            primary_device = "DESKTOP"
            if time_breakdown:
                primary_device = max(time_breakdown.items(), key=lambda x: x[1])[0]

            duration = float(s.get("focused_time_seconds", 0.0) + s.get("interruption_time_seconds", 0.0))

            results.append(
                CrossDeviceSessionRead(
                    session_id=uuid.UUID(s["id"]) if isinstance(s.get("id"), str) else (s.get("id") or uuid.uuid4()),
                    started_at=_to_utc(s["started_at"]),
                    ended_at=_to_utc(s.get("ended_at")),
                    duration_seconds=round(duration, 1),
                    primary_device_type=primary_device,
                    device_transitions_count=device_transitions,
                    device_time_breakdown={k: round(v, 1) for k, v in time_breakdown.items()},
                    cross_device_interruption_seconds=round(cross_device_int_sec, 1),
                    continuity_score=round(float(s.get("reconstruction_confidence", 1.0)), 2),
                    timeline_segments=tl,
                )
            )

        return results
