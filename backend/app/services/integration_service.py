"""Service layer for calendar integrations, credential vaulting, and OAuth management."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.calendar_integration import CalendarCredential, CalendarIntegration, CalendarSyncState
from integrations.app.core.encryption import TokenVault, redact_secret
from integrations.app.core.integration_manager import IntegrationManager
from integrations.app.core.provider_registry import ProviderRegistry
from integrations.app.core.token_manager import TokenManager
from integrations.app.schemas.integration_schemas import (
    CalendarDTO,
    CalendarListResponse,
    ConnectResponse,
    ConnectionStatus,
    IntegrationResponse,
    IntegrationStatusResponse,
    OAuthTokenBundle,
    SyncResult,
    SyncStatus,
)
from integrations.app.synchronization.sync_scheduler import SyncScheduler
from integrations.app.synchronization.sync_state import CalendarSyncTracker

logger = logging.getLogger(__name__)


def get_token_vault() -> TokenVault:
    settings = get_settings()
    return TokenVault(master_secret=settings.SECRET_KEY)


def get_token_manager() -> TokenManager:
    return TokenManager(token_vault=get_token_vault())


def get_integration_manager() -> IntegrationManager:
    settings = get_settings()
    return IntegrationManager(
        token_manager=get_token_manager(),
        hmac_secret=settings.SECRET_KEY,
    )


def list_user_integrations(db: Session, user_id: UUID) -> List[IntegrationResponse]:
    """Retrieve all calendar integrations for the authenticated user."""
    stmt = (
        select(CalendarIntegration)
        .where(CalendarIntegration.user_id == user_id)
        .order_by(CalendarIntegration.created_at.desc())
    )
    integrations = db.scalars(stmt).all()

    responses: List[IntegrationResponse] = []
    for item in integrations:
        # Resolve primary sync state if available
        sync_state = next((s for s in item.sync_states if s.calendar_id == "primary"), None)
        if not sync_state and item.sync_states:
            sync_state = item.sync_states[0]

        responses.append(
            IntegrationResponse(
                id=item.id,
                user_id=item.user_id,
                provider=item.provider,
                provider_account_id=item.provider_account_id,
                provider_email=item.provider_email,
                connection_status=ConnectionStatus(item.connection_status),
                granted_scopes=item.granted_scopes or [],
                last_synced_at=sync_state.last_sync_timestamp if sync_state else None,
                sync_status=SyncStatus(sync_state.sync_status) if sync_state else SyncStatus.INITIALIZING,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return responses


def initiate_connect(
    user_id: UUID,
    provider: str,
    redirect_uri: Optional[str] = None,
    request_write_access: bool = False,
) -> ConnectResponse:
    """Generate authorization URL, state token, and PKCE parameters."""
    manager = get_integration_manager()
    default_redirect = "http://localhost:3000/settings/integrations/callback"
    target_redirect = redirect_uri or default_redirect

    return manager.initiate_connection(
        user_id=user_id,
        provider=provider,
        redirect_uri=target_redirect,
        request_write_access=request_write_access,
    )


def handle_callback(
    db: Session,
    state: str,
    auth_code: str,
    authenticated_user_id: Optional[UUID] = None,
) -> IntegrationResponse:
    """Validate state, exchange auth code for tokens, save encrypted credentials, and trigger initial sync."""
    manager = get_integration_manager()
    token_mgr = get_token_manager()

    user_id, provider, token_bundle = manager.complete_connection(
        state_str=state,
        auth_code=auth_code,
        authenticated_user_id=authenticated_user_id,
    )

    # Encrypt credentials before database insertion
    enc_access, enc_refresh = token_mgr.encrypt_credentials(
        token_bundle=token_bundle,
        user_id=user_id,
        provider=provider,
    )

    # Check for existing integration record for this user and provider
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.provider == provider,
    )
    existing_integration = db.scalars(stmt).first()

    if existing_integration:
        integration = existing_integration
        integration.connection_status = ConnectionStatus.CONNECTED.value
        integration.is_active = True
        integration.granted_scopes = token_bundle.scope
        integration.provider_email = token_bundle.provider_email or integration.provider_email
        integration.provider_account_id = token_bundle.provider_user_id or integration.provider_account_id
        integration.updated_at = datetime.now(timezone.utc)

        # Update or create credential
        if integration.credentials:
            cred = integration.credentials
            cred.encrypted_access_token = enc_access
            if enc_refresh:
                cred.encrypted_refresh_token = enc_refresh
            cred.expiration_timestamp = token_bundle.expires_at
            cred.credential_version += 1
            cred.token_type = token_bundle.token_type
            cred.updated_at = datetime.now(timezone.utc)
        else:
            cred = CalendarCredential(
                integration_id=integration.id,
                encrypted_access_token=enc_access,
                encrypted_refresh_token=enc_refresh,
                expiration_timestamp=token_bundle.expires_at,
                credential_version=1,
                token_type=token_bundle.token_type,
            )
            db.add(cred)
    else:
        integration = CalendarIntegration(
            user_id=user_id,
            provider=provider,
            provider_account_id=token_bundle.provider_user_id,
            provider_email=token_bundle.provider_email,
            connection_status=ConnectionStatus.CONNECTED.value,
            granted_scopes=token_bundle.scope,
            is_active=True,
        )
        db.add(integration)
        db.flush()

        cred = CalendarCredential(
            integration_id=integration.id,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            expiration_timestamp=token_bundle.expires_at,
            credential_version=1,
            token_type=token_bundle.token_type,
        )
        db.add(cred)

        # Create primary sync state
        sync_state = CalendarSyncState(
            integration_id=integration.id,
            calendar_id="primary",
            sync_status=SyncStatus.INITIALIZING.value,
        )
        db.add(sync_state)

    db.commit()
    db.refresh(integration)

    # Perform initial sync
    try:
        synchronize_integration(db, user_id, integration.id)
    except Exception as e:
        logger.warning("Initial synchronization after connect encountered an error: %s", e)

    db.refresh(integration)
    sync_state = next((s for s in integration.sync_states if s.calendar_id == "primary"), None)

    return IntegrationResponse(
        id=integration.id,
        user_id=integration.user_id,
        provider=integration.provider,
        provider_account_id=integration.provider_account_id,
        provider_email=integration.provider_email,
        connection_status=ConnectionStatus(integration.connection_status),
        granted_scopes=integration.granted_scopes or [],
        last_synced_at=sync_state.last_sync_timestamp if sync_state else None,
        sync_status=SyncStatus(sync_state.sync_status) if sync_state else SyncStatus.INITIALIZING,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def disconnect_integration(db: Session, user_id: UUID, integration_id: UUID) -> bool:
    """Disconnect provider, revoke tokens remotely, and mark status as REVOKED."""
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.id == integration_id,
        CalendarIntegration.user_id == user_id,
    )
    integration = db.scalars(stmt).first()
    if not integration:
        return False

    token_mgr = get_token_manager()
    if integration.credentials:
        try:
            bundle = token_mgr.decrypt_credentials(
                encrypted_access_token=integration.credentials.encrypted_access_token,
                encrypted_refresh_token=integration.credentials.encrypted_refresh_token,
                user_id=user_id,
                provider=integration.provider,
                expiration_timestamp=integration.credentials.expiration_timestamp,
            )
            adapter = ProviderRegistry.get_provider(integration.provider)
            adapter.disconnect(bundle)
        except Exception as e:
            logger.warning("Error revoking external token remotely: %s", e)

        # Delete credential record
        db.delete(integration.credentials)

    integration.connection_status = ConnectionStatus.REVOKED.value
    integration.is_active = False
    integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def get_integration_status(db: Session, user_id: UUID, integration_id: UUID) -> Optional[IntegrationStatusResponse]:
    """Retrieve detailed operational status and token health for an integration."""
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.id == integration_id,
        CalendarIntegration.user_id == user_id,
    )
    integration = db.scalars(stmt).first()
    if not integration:
        return None

    sync_state = next((s for s in integration.sync_states if s.calendar_id == "primary"), None)
    now = datetime.now(timezone.utc)
    has_valid_token = False
    expires_in_seconds = None

    if integration.credentials and integration.connection_status == ConnectionStatus.CONNECTED.value:
        exp = integration.credentials.expiration_timestamp
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        diff = int((exp - now).total_seconds())
        expires_in_seconds = max(0, diff)
        has_valid_token = diff > 0 or (integration.credentials.encrypted_refresh_token is not None)

    return IntegrationStatusResponse(
        id=integration.id,
        provider=integration.provider,
        connection_status=ConnectionStatus(integration.connection_status),
        is_active=integration.is_active,
        has_valid_token=has_valid_token,
        expires_in_seconds=expires_in_seconds,
        last_synced_at=sync_state.last_sync_timestamp if sync_state else None,
        sync_status=SyncStatus(sync_state.sync_status) if sync_state else SyncStatus.INITIALIZING,
        error_message=sync_state.error_message if sync_state else None,
    )


def list_user_calendars(db: Session, user_id: UUID) -> List[CalendarListResponse]:
    """Fetch all calendars available across all active user integrations."""
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.connection_status == ConnectionStatus.CONNECTED.value,
        CalendarIntegration.is_active.is_(True),
    )
    integrations = db.scalars(stmt).all()
    token_mgr = get_token_manager()

    results: List[CalendarListResponse] = []
    for integration in integrations:
        if not integration.credentials:
            continue

        try:
            bundle, was_refreshed, new_access, new_refresh = token_mgr.ensure_valid_token(
                encrypted_access_token=integration.credentials.encrypted_access_token,
                encrypted_refresh_token=integration.credentials.encrypted_refresh_token,
                expiration_timestamp=integration.credentials.expiration_timestamp,
                user_id=user_id,
                provider=integration.provider,
                scopes=integration.granted_scopes,
            )
            if was_refreshed:
                integration.credentials.encrypted_access_token = new_access  # type: ignore
                if new_refresh:
                    integration.credentials.encrypted_refresh_token = new_refresh
                integration.credentials.expiration_timestamp = bundle.expires_at
                integration.credentials.credential_version += 1
                db.commit()

            adapter = ProviderRegistry.get_provider(integration.provider)
            calendars = adapter.list_calendars(bundle)
            results.append(
                CalendarListResponse(
                    integration_id=integration.id,
                    provider=integration.provider,
                    calendars=calendars,
                )
            )
        except Exception as e:
            logger.error("Failed to list calendars for %s (%s): %s", integration.id, integration.provider, e)

    return results


def synchronize_integration(db: Session, user_id: UUID, integration_id: UUID) -> SyncResult:
    """Execute initial or incremental sync for an integration."""
    stmt = select(CalendarIntegration).where(
        CalendarIntegration.id == integration_id,
        CalendarIntegration.user_id == user_id,
    )
    integration = db.scalars(stmt).first()
    if not integration or not integration.credentials:
        return SyncResult(success=False, error_message="Integration or credentials not found.")

    token_mgr = get_token_manager()
    bundle, was_refreshed, new_access, new_refresh = token_mgr.ensure_valid_token(
        encrypted_access_token=integration.credentials.encrypted_access_token,
        encrypted_refresh_token=integration.credentials.encrypted_refresh_token,
        expiration_timestamp=integration.credentials.expiration_timestamp,
        user_id=user_id,
        provider=integration.provider,
        scopes=integration.granted_scopes,
    )
    if was_refreshed:
        integration.credentials.encrypted_access_token = new_access  # type: ignore
        if new_refresh:
            integration.credentials.encrypted_refresh_token = new_refresh
        integration.credentials.expiration_timestamp = bundle.expires_at
        integration.credentials.credential_version += 1
        db.commit()

    # Find or create sync state
    sync_state = next((s for s in integration.sync_states if s.calendar_id == "primary"), None)
    if not sync_state:
        sync_state = CalendarSyncState(
            integration_id=integration.id,
            calendar_id="primary",
            sync_status=SyncStatus.INITIALIZING.value,
        )
        db.add(sync_state)
        db.flush()

    tracker = CalendarSyncTracker(
        integration_id=integration.id,
        calendar_id=sync_state.calendar_id,
        sync_token=sync_state.sync_token,
        last_sync_timestamp=sync_state.last_sync_timestamp,
        sync_status=SyncStatus(sync_state.sync_status),
    )

    scheduler = SyncScheduler(token_manager=token_mgr)
    result = scheduler.execute_sync(
        provider=integration.provider,
        credentials=bundle,
        sync_tracker=tracker,
    )

    # Commit updated tracker state to DB
    sync_state.sync_token = tracker.sync_token
    sync_state.last_sync_timestamp = tracker.last_sync_timestamp
    sync_state.sync_status = tracker.sync_status.value
    sync_state.error_message = tracker.error_message
    sync_state.updated_at = datetime.now(timezone.utc)
    db.commit()

    return result
