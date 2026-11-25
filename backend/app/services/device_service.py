"""Device registry service managing hardware authentication, status, and revocation (Phase 5.7)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_device import UserDevice
from app.schemas.device import DeviceRegisterRequest, DeviceUpdateRequest

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceService:
    @classmethod
    def register_device(
        cls,
        db: Session,
        user_id: uuid.UUID,
        request: DeviceRegisterRequest,
    ) -> UserDevice:
        """Registers a new device or updates an existing device record."""
        stmt = select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == request.device_id,
        )
        device = db.scalars(stmt).first()

        now = _utc_now()
        if device:
            # Update existing device and clear revocation if re-registered
            device.device_name = request.device_name
            device.device_type = request.device_type
            device.platform = request.platform
            device.application_version = request.application_version
            if request.device_metadata:
                device.device_metadata = {**device.device_metadata, **request.device_metadata}
            device.last_seen_timestamp = now
            device.connection_status = "ONLINE"
            device.synchronization_status = "SYNCED"
            device.is_active = True
            device.revoked_at = None
        else:
            device = UserDevice(
                user_id=user_id,
                device_id=request.device_id,
                device_type=request.device_type,
                platform=request.platform,
                device_name=request.device_name,
                application_version=request.application_version,
                device_metadata=request.device_metadata or {},
                registration_timestamp=now,
                last_seen_timestamp=now,
                connection_status="ONLINE",
                synchronization_status="SYNCED",
                is_active=True,
            )
            db.add(device)

        db.commit()
        db.refresh(device)
        logger.info(f"Device registered for user {user_id}: {device.device_id} ({device.device_name})")
        return device

    @classmethod
    def list_devices(cls, db: Session, user_id: uuid.UUID) -> List[UserDevice]:
        """Lists all registered devices for the user."""
        stmt = (
            select(UserDevice)
            .where(UserDevice.user_id == user_id)
            .order_by(UserDevice.last_seen_timestamp.desc())
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def get_device(cls, db: Session, user_id: uuid.UUID, device_id: str) -> Optional[UserDevice]:
        """Retrieves a single device by ID."""
        stmt = select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == device_id,
        )
        return db.scalars(stmt).first()

    @classmethod
    def touch_device(
        cls,
        db: Session,
        user_id: uuid.UUID,
        device_id: str,
        platform: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> UserDevice:
        """Updates last_seen timestamp and connection status when telemetry arrives."""
        device = cls.get_device(db, user_id, device_id)
        now = _utc_now()
        if not device:
            # Auto-register device on first contact
            device = UserDevice(
                user_id=user_id,
                device_id=device_id,
                device_type=device_type or "DESKTOP",
                platform=platform or "WINDOWS",
                device_name=f"{platform or 'Device'} ({device_id[:8]})",
                registration_timestamp=now,
                last_seen_timestamp=now,
                connection_status="ONLINE",
                synchronization_status="SYNCED",
                is_active=True,
            )
            db.add(device)
        else:
            if not device.is_active or device.connection_status == "REVOKED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Device '{device_id}' access has been revoked by user.",
                )
            device.last_seen_timestamp = now
            device.connection_status = "ONLINE"

        db.commit()
        db.refresh(device)
        return device

    @classmethod
    def revoke_device(cls, db: Session, user_id: uuid.UUID, device_id: str) -> UserDevice:
        """Revokes authorization for a device, preventing future telemetry sync."""
        device = cls.get_device(db, user_id, device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device '{device_id}' not found.",
            )

        now = _utc_now()
        device.is_active = False
        device.connection_status = "REVOKED"
        device.revoked_at = now
        db.commit()
        db.refresh(device)
        logger.warning(f"Device revoked: {device_id} for user {user_id}")
        return device

    @classmethod
    def verify_device_active(cls, db: Session, user_id: uuid.UUID, device_id: str) -> UserDevice:
        """Validates that device is registered and not revoked."""
        device = cls.get_device(db, user_id, device_id)
        if device and (not device.is_active or device.connection_status == "REVOKED"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Device '{device_id}' has been revoked. Access denied.",
            )
        if not device:
            # Auto-register on first contact
            return cls.touch_device(db, user_id, device_id)
        return device
