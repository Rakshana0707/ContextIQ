"""Integration manager governing OAuth state generation, PKCE verification, and connect/disconnect workflows."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from integrations.app.core.encryption import TokenVault
from integrations.app.core.provider_registry import ProviderRegistry
from integrations.app.core.token_manager import TokenManager
from integrations.app.schemas.integration_schemas import (
    ConnectResponse,
    OAuthTokenBundle,
)

logger = logging.getLogger(__name__)


class OAuthStateError(Exception):
    """Raised when OAuth state token validation fails or expires."""
    pass


class IntegrationManager:
    """Coordinates OAuth flows, PKCE, state tokens, and connection lifecycle."""

    def __init__(self, token_manager: TokenManager, hmac_secret: str):
        self.token_manager = token_manager
        self.hmac_secret = hmac_secret.encode("utf-8")

    @staticmethod
    def generate_pkce() -> Tuple[str, str]:
        """Generate high-entropy code_verifier and S256 code_challenge (RFC 7636)."""
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    def generate_state(
        self,
        user_id: UUID,
        provider: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
        ttl_seconds: int = 600,
    ) -> str:
        """Create tamper-proof, timestamped, HMAC-signed OAuth state string."""
        payload = {
            "uid": str(user_id),
            "p": provider,
            "r": redirect_uri,
            "cv": code_verifier or "",
            "ts": int(time.time()),
            "exp": int(time.time()) + ttl_seconds,
            "n": secrets.token_hex(8),
        }
        raw_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(self.hmac_secret, raw_json, hashlib.sha256).digest()
        envelope = {
            "p": base64.urlsafe_b64encode(raw_json).decode("ascii"),
            "s": base64.urlsafe_b64encode(signature).decode("ascii"),
        }
        return base64.urlsafe_b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")

    def validate_state(self, state_str: str) -> Dict[str, Any]:
        """Validate HMAC signature and expiration on state token. Returns inner payload."""
        try:
            envelope_bytes = base64.urlsafe_b64decode(state_str.encode("ascii"))
            envelope = json.loads(envelope_bytes)
            raw_json = base64.urlsafe_b64decode(envelope["p"].encode("ascii"))
            signature = base64.urlsafe_b64decode(envelope["s"].encode("ascii"))
        except Exception as e:
            raise OAuthStateError(f"Malformed OAuth state token: {e}") from e

        expected_sig = hmac.new(self.hmac_secret, raw_json, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_sig):
            raise OAuthStateError("OAuth state signature mismatch; potential CSRF tampering detected.")

        payload = json.loads(raw_json)
        now = int(time.time())
        if now > payload.get("exp", 0):
            raise OAuthStateError("OAuth state token has expired. Please initiate connection again.")

        return payload

    def initiate_connection(
        self,
        user_id: UUID,
        provider: str,
        redirect_uri: str,
        request_write_access: bool = False,
    ) -> ConnectResponse:
        """Start OAuth flow: generates PKCE, state token, and provider authorization URL."""
        code_verifier, code_challenge = self.generate_pkce()
        state = self.generate_state(
            user_id=user_id,
            provider=provider,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

        provider_adapter = ProviderRegistry.get_provider(provider)
        auth_url = provider_adapter.get_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
            request_write_access=request_write_access,
        )

        return ConnectResponse(
            provider=provider,
            authorization_url=auth_url,
            state=state,
            code_verifier=code_verifier,
        )

    def complete_connection(
        self,
        state_str: str,
        auth_code: str,
        authenticated_user_id: Optional[UUID] = None,
    ) -> Tuple[UUID, str, OAuthTokenBundle]:
        """Validate state, exchange auth code, and return authenticated token bundle."""
        payload = self.validate_state(state_str)
        state_user_id = UUID(payload["uid"])
        provider = payload["p"]
        redirect_uri = payload["r"]
        code_verifier = payload.get("cv") or None

        if authenticated_user_id and state_user_id != authenticated_user_id:
            raise OAuthStateError("Authenticated user does not match OAuth state initiator.")

        provider_adapter = ProviderRegistry.get_provider(provider)
        token_bundle = provider_adapter.authenticate(
            auth_code=auth_code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

        return state_user_id, provider, token_bundle
