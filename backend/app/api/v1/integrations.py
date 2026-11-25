"""REST API router for external calendar integrations, OAuth flows, and status."""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.calendar_integration import (
    CalendarListResponse,
    ConnectRequest,
    ConnectResponse,
    IntegrationResponse,
    IntegrationStatusResponse,
    SyncResult,
)
from app.services import integration_service
from integrations.app.core.integration_manager import OAuthStateError
from integrations.app.core.provider_registry import ProviderRegistry, UnsupportedProviderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=List[IntegrationResponse])
def list_integrations(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieve all connected calendar integrations for the authenticated user."""
    return integration_service.list_user_integrations(db, user_id)


@router.get("/calendars", response_model=List[CalendarListResponse])
def list_calendars(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List calendars across all active integrations for the authenticated user."""
    return integration_service.list_user_calendars(db, user_id)


@router.post("/{provider}/connect", response_model=ConnectResponse)
def connect_provider(
    provider: str,
    payload: Optional[ConnectRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Initiate OAuth flow: returns provider authorization URL, state token, and PKCE parameters."""
    req_write = payload.request_write_access if payload else False
    redirect_uri = payload.redirect_uri if payload else None

    try:
        return integration_service.initiate_connect(
            user_id=user_id,
            provider=provider,
            redirect_uri=redirect_uri,
            request_write_access=req_write,
        )
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{provider}/callback")
def oauth_callback(
    provider: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    """Handle OAuth redirect callback from external provider (Google / Microsoft)."""
    if error:
        logger.warning("OAuth provider returned error: %s", error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authorization was denied or failed: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'code' or 'state' parameters in OAuth callback.",
        )

    try:
        integration = integration_service.handle_callback(
            db=db,
            state=state,
            auth_code=code,
            authenticated_user_id=user_id,
        )
        return integration
    except OAuthStateError as exc:
        logger.error("OAuth state validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("OAuth callback processing error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete calendar integration: {exc}",
        ) from exc


@router.get("/{integration_id}/status", response_model=IntegrationStatusResponse)
def get_integration_status(
    integration_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Inspect integration health, token expiration, and synchronization status."""
    status_resp = integration_service.get_integration_status(db, user_id, integration_id)
    if not status_resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or not owned by user.",
        )
    return status_resp


@router.post("/{integration_id}/disconnect", status_code=status.HTTP_200_OK)
def disconnect_integration(
    integration_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Disconnect provider, revoke credentials remotely, and wipe stored tokens."""
    success = integration_service.disconnect_integration(db, user_id, integration_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or not owned by user.",
        )
    return {"message": "Integration successfully disconnected and tokens revoked.", "id": integration_id}


@router.post("/{integration_id}/sync", response_model=SyncResult)
def trigger_sync(
    integration_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Trigger on-demand synchronization for an integration."""
    result = integration_service.synchronize_integration(db, user_id, integration_id)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.error_message or "Synchronization failed.",
        )
    return result
