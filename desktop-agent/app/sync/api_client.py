"""HTTP API client for ContextIQ server communications."""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class BatchSyncResult:
    """Detailed result of batch synchronization request."""
    success: bool
    synced_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None


class ContextIQApiClient:
    """REST client interacting with ContextIQ backend endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        api_token: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

    def _get_headers(
        self,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        if user_id:
            headers["X-User-ID"] = user_id
        if device_id:
            headers["X-Device-ID"] = device_id
        return headers

    def get_privacy_settings(self, user_id: str) -> Optional[dict[str, Any]]:
        """Fetch user privacy settings (pause status, retention days)."""
        url = f"{self.base_url}/privacy/settings"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(user_id=user_id), params={"user_id": user_id})
                if resp.status_code == 200:
                    return resp.json()
                logger.debug("Failed to get privacy settings: status %d", resp.status_code)
                return None
        except Exception as e:
            logger.debug("Network error fetching privacy settings: %s", e)
            return None

    def get_active_consent(self, user_id: str) -> Optional[dict[str, Any]]:
        """Fetch active telemetry consent for user."""
        url = f"{self.base_url}/privacy/consent"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(user_id=user_id), params={"user_id": user_id})
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
                resp = client.get(url, headers=self._get_headers(user_id=user_id), params={"user_id": user_id})
                if resp.status_code == 200:
                    return resp.json()
                return []
        except Exception as e:
            logger.debug("Network error fetching exclusions: %s", e)
            return []

    def upload_telemetry_batch(
        self,
        events: list[dict[str, Any]],
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> BatchSyncResult:
        """Post a batch of telemetry events to server batch ingestion endpoint."""
        if not events:
            return BatchSyncResult(success=True)

        event_ids = [e["event_id"] for e in events]
        url = f"{self.base_url}/telemetry/events/batch"
        payload = {"events": events}

        start_time = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    headers=self._get_headers(user_id=user_id, device_id=device_id),
                    json=payload,
                )
                latency_ms = (time.monotonic() - start_time) * 1000.0

                if resp.status_code in (200, 201, 202, 204):
                    data = resp.json() if resp.status_code != 204 else {}
                    synced_ids = data.get("synced_event_ids") or event_ids
                    duplicate_ids = data.get("duplicate_event_ids", [])
                    failed_ids = data.get("failed_event_ids", [])
                    return BatchSyncResult(
                        success=True,
                        synced_ids=synced_ids,
                        duplicate_ids=duplicate_ids,
                        failed_ids=failed_ids,
                        latency_ms=round(latency_ms, 2),
                    )
                else:
                    logger.warning(
                        "Server rejected telemetry batch: HTTP %d - %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return BatchSyncResult(
                        success=False,
                        failed_ids=event_ids,
                        latency_ms=round(latency_ms, 2),
                        error_message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000.0
            logger.warning("Failed to upload telemetry batch: %s", e)
            return BatchSyncResult(
                success=False,
                failed_ids=event_ids,
                latency_ms=round(latency_ms, 2),
                error_message=str(e),
            )
