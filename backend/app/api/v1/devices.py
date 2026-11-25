"""FastAPI router for device registry and hardware authorization (ContextIQ Phase 5.7)."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.device import DeviceRead, DeviceRegisterRequest, DeviceRevokeResponse
from app.services.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=List[DeviceRead], summary="List Registered Devices")
def list_devices(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Returns all registered devices for the authenticated user."""
    return DeviceService.list_devices(db=db, user_id=user_id)


@router.post("/register", response_model=DeviceRead, status_code=status.HTTP_201_CREATED, summary="Register or Update Device")
def register_device(
    payload: DeviceRegisterRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Registers a new desktop, mobile, tablet, or web client, or updates its metadata."""
    return DeviceService.register_device(db=db, user_id=user_id, request=payload)


@router.delete("/{device_id}", response_model=DeviceRevokeResponse, summary="Revoke Device Access")
def revoke_device(
    device_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Revokes device access, immediately disabling telemetry synchronization."""
    device = DeviceService.revoke_device(db=db, user_id=user_id, device_id=device_id)
    return DeviceRevokeResponse(
        device_id=device.device_id,
        status=device.connection_status,
        revoked_at=device.revoked_at or device.updated_at,
    )
