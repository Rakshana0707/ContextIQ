"""
Event Ingestion and Processing Pipeline (ContextIQ Phase 7.3).
Provides:
- Standardized event routing and filtering
- Deduplication via idempotency keys
- Telemetry consent authorization enforcement
- Dead-letter handling with diagnostic error reasons
- Automation rule evaluation dispatch (Phase 7.2 engine integration)
- Proactive intelligence feed item generation
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.event_models import (
    DeadLetterEventRecord,
    StandardEventRecord,
)
from app.models.telemetry_consent import ConsentStatus, TelemetryConsent
from app.schemas.event_schemas import (
    EventIngestRequest,
    EventProcessingResult,
    EventSource,
    StandardEvent,
    StandardEventType,
)
from app.services.automation_engine import AutomationRuleEvaluator
from app.services.proactive_intelligence import ProactiveIntelligenceService

logger = logging.getLogger(__name__)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class EventProcessor:
    """
    Core event orchestrator.
    Handles validation, deduplication, consent checking, rule evaluation,
    proactive feed generation, and dead-letter routing.
    """

    BEHAVIORAL_RISK_EVENTS = {
        StandardEventType.THRASHING_DETECTED.value,
        StandardEventType.FORGETTING_RISK_SPIKE.value,
        StandardEventType.RECOVERY_LAG_EXCEEDED.value,
        StandardEventType.MISSED_RESUMPTION.value,
        StandardEventType.CALENDAR_OVERLOAD.value,
        StandardEventType.BFI_SPIKE.value,
        StandardEventType.FOCUS_PATTERN_DRIFT.value,
    }

    @classmethod
    def record_dead_letter(
        cls,
        db: Session,
        raw_payload: Dict[str, Any],
        error_code: str,
        error_reason: str,
        user_id: Optional[uuid.UUID] = None,
        event_id: Optional[str] = None,
    ) -> DeadLetterEventRecord:
        """Stores unparseable, unauthorized, or failing events in dead-letter store."""
        dl_record = DeadLetterEventRecord(
            event_id=event_id,
            user_id=user_id,
            raw_payload=raw_payload,
            error_code=error_code,
            error_reason=error_reason,
            retry_count=0,
            max_retries=3,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(dl_record)
        db.commit()
        db.refresh(dl_record)
        return dl_record

    @classmethod
    def process_event(
        cls,
        db: Session,
        event_or_req: Union[StandardEvent, EventIngestRequest, Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> EventProcessingResult:
        """
        Main pipeline entrypoint.
        Processes an incoming event through validation, deduplication, consent,
        rule execution, and proactive intelligence generation.
        """
        current_time = _ensure_utc(now) or datetime.now(timezone.utc)

        # 1. Standardize and validate input
        try:
            if isinstance(event_or_req, StandardEvent):
                event = event_or_req
            elif isinstance(event_or_req, EventIngestRequest):
                event = StandardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=event_or_req.event_type,
                    user_id=event_or_req.user_id,
                    device_id=event_or_req.device_id,
                    event_timestamp=_ensure_utc(event_or_req.event_timestamp) or current_time,
                    ingestion_timestamp=current_time,
                    source=event_or_req.source or EventSource.DESKTOP_TELEMETRY.value,
                    payload=event_or_req.payload,
                    correlation_id=event_or_req.correlation_id,
                    idempotency_key=event_or_req.idempotency_key,
                )
            elif isinstance(event_or_req, dict):
                event = StandardEvent(**event_or_req)
            else:
                raise ValueError(f"Unsupported event payload type: {type(event_or_req)}")
        except Exception as ex:
            raw_dict = event_or_req if isinstance(event_or_req, dict) else getattr(event_or_req, "__dict__", {})
            cls.record_dead_letter(
                db=db,
                raw_payload=raw_dict,
                error_code="VALIDATION_FAILED",
                error_reason=str(ex),
            )
            return EventProcessingResult(
                event_id="unknown",
                status="DEAD_LETTER",
                rationale=f"Event validation failed: {str(ex)}",
            )

        # 2. Check Deduplication / Idempotency
        if event.idempotency_key:
            existing_event = db.execute(
                select(StandardEventRecord).where(
                    and_(
                        StandardEventRecord.user_id == event.user_id,
                        StandardEventRecord.idempotency_key == event.idempotency_key,
                    )
                )
            ).scalar_one_or_none()

            if existing_event:
                return EventProcessingResult(
                    event_id=existing_event.event_id,
                    status="DUPLICATE",
                    is_duplicate=True,
                    rationale=f"Event with idempotency_key '{event.idempotency_key}' was already ingested.",
                )

        # Also check event_id primary key collision
        existing_by_id = db.execute(
            select(StandardEventRecord).where(StandardEventRecord.event_id == event.event_id)
        ).scalar_one_or_none()
        if existing_by_id:
            return EventProcessingResult(
                event_id=existing_by_id.event_id,
                status="DUPLICATE",
                is_duplicate=True,
                rationale=f"Event ID '{event.event_id}' already exists in event stream.",
            )

        # 3. Telemetry Consent Verification
        if event.source in (EventSource.DESKTOP_TELEMETRY.value, EventSource.MOBILE_COMPANION.value):
            consent = db.execute(
                select(TelemetryConsent).where(
                    and_(
                        TelemetryConsent.user_id == event.user_id,
                        TelemetryConsent.consent_status == "GRANTED",
                    )
                )
            ).scalar_one_or_none()

            if not consent:
                cls.record_dead_letter(
                    db=db,
                    raw_payload=event.model_dump(mode="json"),
                    error_code="CONSENT_REQUIRED",
                    error_reason="Telemetry event rejected: user has not granted active telemetry consent.",
                    user_id=event.user_id,
                    event_id=event.event_id,
                )
                return EventProcessingResult(
                    event_id=event.event_id,
                    status="DEAD_LETTER",
                    rationale="Telemetry event dropped: telemetry consent is not granted for this user.",
                )

        # 4. Durable Event Stream Persistence
        event_record = StandardEventRecord(
            event_id=event.event_id,
            user_id=event.user_id,
            device_id=event.device_id,
            event_type=event.event_type,
            event_timestamp=_ensure_utc(event.event_timestamp),
            ingestion_timestamp=current_time,
            schema_version=event.schema_version,
            source=event.source,
            payload=event.payload,
            correlation_id=event.correlation_id,
            idempotency_key=event.idempotency_key,
            processed=False,
            rules_matched=0,
            created_at=current_time,
            updated_at=current_time,
        )
        db.add(event_record)
        db.flush()

        # 5. User-Defined Automation Rules Evaluation (Phase 7.2 Integration)
        matched_rules_count = 0
        executions_created_count = 0
        try:
            rule_results = AutomationRuleEvaluator.evaluate_event(
                db=db,
                user_id=event.user_id,
                event_type=event.event_type,
                event_payload=event.payload,
                as_of=current_time,
            )
            matched_rules_count = len(rule_results)
            executions_created_count = sum(1 for r in rule_results if r.status in ("PENDING", "APPROVED", "COMPLETED"))
        except Exception as ex:
            logger.error(f"Rule evaluation encountered error for event {event.event_id}: {ex}")

        event_record.rules_matched = matched_rules_count
        event_record.processed = True

        # 6. Proactive Intelligence Feed Generation (Phase 7.3)
        feed_item_created = False
        feed_item_id: Optional[uuid.UUID] = None
        suppressed_by_fatigue = False
        rationale: Optional[str] = None

        if event.event_type in cls.BEHAVIORAL_RISK_EVENTS:
            feed_item, suppress_reason = ProactiveIntelligenceService.generate_feed_item_from_event(
                db=db,
                event=event,
                now=current_time,
                force=False,
            )
            if feed_item:
                feed_item_created = True
                feed_item_id = feed_item.id
                rationale = "Proactive intelligence insight generated and posted to user feed."
            else:
                suppressed_by_fatigue = True
                rationale = f"Proactive alert suppressed: {suppress_reason}"
        else:
            rationale = "Event processed successfully."

        db.commit()

        return EventProcessingResult(
            event_id=event.event_id,
            status="PROCESSED",
            is_duplicate=False,
            rules_matched=matched_rules_count,
            executions_created=executions_created_count,
            proactive_feed_item_created=feed_item_created,
            proactive_feed_item_id=feed_item_id,
            suppressed_by_fatigue=suppressed_by_fatigue,
            rationale=rationale,
        )
