"""Token manager for secure OAuth token lifecycle, encryption, rotation, and validation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from uuid import UUID

from integrations.app.core.encryption import TokenVault, redact_secret
from integrations.app.core.provider_registry import ProviderRegistry
from integrations.app.schemas.integration_schemas import OAuthTokenBundle

logger = logging.getLogger(__name__)


class TokenSecurityError(Exception):
    """Raised when token validation, ownership, or security checks fail."""
    pass


class TokenManager:
    """Manages token encryption, decryption, auto-refresh, and credential version rotation."""

    def __init__(self, token_vault: TokenVault):
        self.vault = token_vault

    def encrypt_credentials(
        self,
        token_bundle: OAuthTokenBundle,
        user_id: UUID,
        provider: str,
    ) -> Tuple[bytes, Optional[bytes]]:
        """Encrypt access and refresh tokens with user & provider binding."""
        aad = f"{user_id}:{provider}"
        encrypted_access = self.vault.encrypt(token_bundle.access_token, associated_data=aad)
        encrypted_refresh = None
        if token_bundle.refresh_token:
            encrypted_refresh = self.vault.encrypt(token_bundle.refresh_token, associated_data=aad)
        return encrypted_access, encrypted_refresh

    def decrypt_credentials(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: Optional[bytes],
        user_id: UUID,
        provider: str,
        expiration_timestamp: datetime,
        scopes: Optional[list[str]] = None,
    ) -> OAuthTokenBundle:
        """Decrypt tokens and validate ownership via AAD."""
        aad = f"{user_id}:{provider}"
        try:
            access_token = self.vault.decrypt(encrypted_access_token, associated_data=aad)
        except Exception as e:
            logger.error("Failed to decrypt access token for user %s: %s", user_id, redact_secret(str(e)))
            raise TokenSecurityError(f"Access token decryption failed or ownership mismatch: {e}") from e

        refresh_token = None
        if encrypted_refresh_token:
            try:
                refresh_token = self.vault.decrypt(encrypted_refresh_token, associated_data=aad)
            except Exception as e:
                logger.error("Failed to decrypt refresh token for user %s: %s", user_id, redact_secret(str(e)))
                raise TokenSecurityError(f"Refresh token decryption failed or ownership mismatch: {e}") from e

        return OAuthTokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expiration_timestamp,
            scope=scopes or [],
        )

    def is_token_expired(self, expires_at: datetime, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or within the refresh buffer window (default 5 min)."""
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return (expires_at - timedelta(seconds=buffer_seconds)) <= now

    def ensure_valid_token(
        self,
        encrypted_access_token: bytes,
        encrypted_refresh_token: Optional[bytes],
        expiration_timestamp: datetime,
        user_id: UUID,
        provider: str,
        scopes: Optional[list[str]] = None,
    ) -> Tuple[OAuthTokenBundle, bool, Optional[bytes], Optional[bytes]]:
        """Validate token; if expired and refresh token available, auto-refreshes credentials.

        Returns: (token_bundle, was_refreshed, new_encrypted_access, new_encrypted_refresh)
        """
        bundle = self.decrypt_credentials(
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            user_id=user_id,
            provider=provider,
            expiration_timestamp=expiration_timestamp,
            scopes=scopes,
        )

        if not self.is_token_expired(bundle.expires_at):
            return bundle, False, None, None

        if not bundle.refresh_token:
            raise TokenSecurityError("Access token is expired and no refresh token is available.")

        logger.info("Access token expired for user %s (%s). Performing automated token refresh.", user_id, provider)
        provider_adapter = ProviderRegistry.get_provider(provider)
        refreshed_bundle = provider_adapter.refresh_credentials(bundle.refresh_token)

        # Encrypt updated credentials
        new_enc_access, new_enc_refresh = self.encrypt_credentials(
            token_bundle=refreshed_bundle,
            user_id=user_id,
            provider=provider,
        )
        return refreshed_bundle, True, new_enc_access, new_enc_refresh
