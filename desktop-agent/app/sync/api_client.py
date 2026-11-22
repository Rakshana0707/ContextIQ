"""HTTP API client for ContextIQ server communications."""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ContextIQApiClient:
    """REST client interacting with ContextIQ backend endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1", api_token: str | None = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

    def _get_headers(self, user_id: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        if user_id:
            # Send test user ID header if configured
            headers["X-User-ID"] = user_id
        return headers

    def get_privacy_settings(self, user_id: str) -> dict[str, Any] | None:
        """Fetch user privacy settings (pause status, retention days)."""
        url = f"{self.base_url}/privacy/settings"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(user_id), params={"user_id": user_id})
                if resp.status_code == 200:
                    return resp.json()
                logger.debug("Failed to get privacy settings: status %d", resp.status_code)
                return None
        except Exception as e:
            logger.debug("Network error fetching privacy settings: %s", e)
            return None

    def get_active_consent(self, user_id: str) -> dict[str, Any] | None:
        """Fetch active telemetry consent for user."""
        url = f"{self.base_url}/privacy/consent"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(user_id), params={"user_id": user_id})
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception as e:
            logger.debug("Network error fetching active consent: %s", e)
            return None

    def get_app_exclusions(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch user application exclusion rules."""
        url = f"{self.base_url}/privacy/exclusions"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(user_id), params={"user_id": user_id})
                if resp.status_code == 200:
                    return resp.json()
                return []
        except Exception as e:
            logger.debug("Network error fetching exclusions: %s", e)
            return []

    def upload_telemetry_batch(self, events: list[dict[str, Any]], user_id: str | None = None) -> bool:
        """Post a batch of telemetry events to server ingestion endpoint."""
        if not events:
            return True
        url = f"{self.base_url}/telemetry/events"
        payload = {"events": events}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self._get_headers(user_id), json=payload)
                if resp.status_code in (200, 201, 202, 204):
                    return True
                logger.warning("Server rejected telemetry batch: HTTP %d - %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.warning("Failed to upload telemetry batch to %s: %s", url, e)
            return False
