import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.privacy import (
    AppExclusionCreate,
    AppExclusionRead,
    ConsentGrantRequest,
    ConsentRead,
    ConsentRevokeRequest,
    DataPurgeRequest,
    DataPurgeResponse,
    PrivacySettingsRead,
    PrivacySettingsUpdate,
    TelemetryMetadataSummary,
)
from app.services import privacy_service

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/consent", response_model=Optional[ConsentRead])
def get_current_consent(
    device_id: Optional[str] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieve the user's latest active telemetry consent status."""
    return privacy_service.get_active_consent(db, user_id, device_id)


@router.post("/consent", response_model=ConsentRead, status_code=status.HTTP_201_CREATED)
def grant_or_update_consent(
    payload: ConsentGrantRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Explicitly grant or update telemetry consent.
    Creates an immutable, versioned audit record.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return privacy_service.grant_consent(db, user_id, payload, ip_address=ip, user_agent=ua)


@router.post("/consent/revoke", response_model=ConsentRead)
def revoke_consent(
    payload: ConsentRevokeRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Revoke telemetry consent immediately.
    Halts automated desktop collection and appends a revocation audit log.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return privacy_service.revoke_consent(db, user_id, payload, ip_address=ip, user_agent=ua)


@router.get("/consent/history", response_model=list[ConsentRead])
def get_consent_history(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieve complete immutable audit trail of granted, updated, and revoked consent."""
    return privacy_service.get_consent_history(db, user_id)


@router.get("/settings", response_model=PrivacySettingsRead)
def get_privacy_settings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get active privacy controls, pause state, and data retention thresholds."""
    return privacy_service.get_or_create_privacy_settings(db, user_id)


@router.patch("/settings", response_model=PrivacySettingsRead)
def update_privacy_settings(
    payload: PrivacySettingsUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update privacy configurations (pause/resume collection, retention days)."""
    return privacy_service.update_privacy_settings(db, user_id, payload)


@router.get("/exclusions", response_model=list[AppExclusionRead])
def list_app_exclusions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List applications excluded from behavioral telemetry monitoring."""
    return privacy_service.list_app_exclusions(db, user_id)


@router.post("/exclusions", response_model=AppExclusionRead, status_code=status.HTTP_201_CREATED)
def add_app_exclusion(
    payload: AppExclusionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Add a desktop process to the privacy exclusion list (e.g. '1password.exe')."""
    return privacy_service.add_app_exclusion(db, user_id, payload)


@router.delete("/exclusions/{exclusion_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_app_exclusion(
    exclusion_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Remove an application from the privacy exclusion list."""
    privacy_service.remove_app_exclusion(db, user_id, exclusion_id)


@router.post("/data/purge", response_model=DataPurgeResponse)
def purge_telemetry_data(
    payload: DataPurgeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    GDPR Article 17 Right to Erasure.
    Permanently purges synchronized raw telemetry and optional context sessions.
    """
    return privacy_service.purge_user_telemetry(db, user_id, payload)


@router.get("/metadata", response_model=TelemetryMetadataSummary)
def get_telemetry_metadata(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Summary of collected telemetry metadata, event volumes, and storage boundaries."""
    return privacy_service.get_metadata_summary(db, user_id)
