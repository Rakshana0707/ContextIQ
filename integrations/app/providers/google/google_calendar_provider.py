"""Google Calendar API v3 provider adapter."""
from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

from integrations.app.core.encryption import redact_secret
from integrations.app.providers.base_calendar_provider import BaseCalendarProvider
from integrations.app.schemas.integration_schemas import (
    CalendarDTO,
    CalendarEventCreateDTO,
    CalendarEventDTO,
    CalendarEventUpdateDTO,
    EventStatus,
    EventTransparency,
    OAuthTokenBundle,
    SyncResult,
)

logger = logging.getLogger(__name__)


class GoogleCalendarProvider(BaseCalendarProvider):
    """Google Calendar implementation of BaseCalendarProvider."""

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    API_BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(
        self,
        client_id: str = "google-client-id-placeholder",
        client_secret: str = "google-client-secret-placeholder",
        timeout: float = 10.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout

    @property
    def provider_id(self) -> str:
        return "google_calendar"

    @property
    def provider_name(self) -> str:
        return "Google Calendar"

    @property
    def default_scopes(self) -> List[str]:
        return [
            "https://www.googleapis.com/auth/calendar.events.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
        ]

    @property
    def write_scopes(self) -> List[str]:
        return [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/userinfo.email",
        ]

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        code_challenge: Optional[str] = None,
        request_write_access: bool = False,
    ) -> str:
        scopes = self.write_scopes if request_write_access else self.default_scopes
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    def authenticate(
        self,
        auth_code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
        **kwargs: Any,
    ) -> OAuthTokenBundle:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            payload["code_verifier"] = code_verifier

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.TOKEN_URL, data=payload)
            if resp.status_code != 200:
                logger.error("Google OAuth token exchange failed: status=%d, body=%s", resp.status_code, redact_secret(resp.text))
                raise ValueError(f"Google authentication failed: HTTP {resp.status_code}")
            data = resp.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        granted_scope = data.get("scope", "").split(" ") if data.get("scope") else self.default_scopes

        # Retrieve user email/id from userinfo if accessible
        provider_email = None
        provider_user_id = None
        access_token = data["access_token"]
        try:
            with httpx.Client(timeout=self.timeout) as client:
                u_resp = client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if u_resp.status_code == 200:
                    u_data = u_resp.json()
                    provider_email = u_data.get("email")
                    provider_user_id = u_data.get("id")
        except Exception as e:
            logger.debug("Failed to retrieve Google userinfo: %s", e)

        return OAuthTokenBundle(
            access_token=access_token,
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=granted_scope,
            id_token=data.get("id_token"),
            provider_user_id=provider_user_id,
            provider_email=provider_email,
        )

    def refresh_credentials(self, refresh_token: str) -> OAuthTokenBundle:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.TOKEN_URL, data=payload)
            if resp.status_code != 200:
                logger.error("Google token refresh failed: status=%d, body=%s", resp.status_code, redact_secret(resp.text))
                raise ValueError(f"Google token refresh failed: HTTP {resp.status_code}")
            data = resp.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        granted_scope = data.get("scope", "").split(" ") if data.get("scope") else self.default_scopes
        new_refresh = data.get("refresh_token") or refresh_token

        return OAuthTokenBundle(
            access_token=data["access_token"],
            refresh_token=new_refresh,
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=granted_scope,
        )

    def list_calendars(self, credentials: OAuthTokenBundle) -> List[CalendarDTO]:
        url = f"{self.API_BASE}/users/me/calendarList"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        calendars: List[CalendarDTO] = []

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error("Google list_calendars failed: HTTP %d", resp.status_code)
                return []
            items = resp.json().get("items", [])
            for item in items:
                calendars.append(
                    CalendarDTO(
                        calendar_id=item.get("id", "primary"),
                        name=item.get("summary", "Calendar"),
                        is_primary=bool(item.get("primary", False)),
                        access_role=item.get("accessRole", "reader"),
                        description=item.get("description"),
                        time_zone=item.get("timeZone"),
                    )
                )
        return calendars

    def list_events(
        self,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime,
        credentials: OAuthTokenBundle,
    ) -> List[CalendarEventDTO]:
        url = f"{self.API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        params = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.error("Google list_events failed: HTTP %d", resp.status_code)
                return []
            items = resp.json().get("items", [])
            return [self._parse_google_event(item, calendar_id) for item in items]

    def get_event(
        self,
        calendar_id: str,
        event_id: str,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        url = f"{self.API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events/{urllib.parse.quote(event_id)}"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Google event not found: HTTP {resp.status_code}")
            return self._parse_google_event(resp.json(), calendar_id)

    def create_event(
        self,
        calendar_id: str,
        event: CalendarEventCreateDTO,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        url = f"{self.API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events"
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "summary": event.title,
            "description": event.description,
            "location": event.location_name,
            "transparency": "opaque" if event.transparency == EventTransparency.OPAQUE else "transparent",
        }
        if event.is_all_day:
            payload["start"] = {"date": event.start_time.strftime("%Y-%m-%d")}
            payload["end"] = {"date": event.end_time.strftime("%Y-%m-%d")}
        else:
            payload["start"] = {"dateTime": event.start_time.isoformat()}
            payload["end"] = {"dateTime": event.end_time.isoformat()}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                raise ValueError(f"Failed to create Google event: HTTP {resp.status_code} - {resp.text}")
            return self._parse_google_event(resp.json(), calendar_id)

    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: CalendarEventUpdateDTO,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        url = f"{self.API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events/{urllib.parse.quote(event_id)}"
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "Content-Type": "application/json",
        }
        patch_payload: Dict[str, Any] = {}
        if updates.title is not None:
            patch_payload["summary"] = updates.title
        if updates.description is not None:
            patch_payload["description"] = updates.description
        if updates.location_name is not None:
            patch_payload["location"] = updates.location_name
        if updates.transparency is not None:
            patch_payload["transparency"] = "opaque" if updates.transparency == EventTransparency.OPAQUE else "transparent"
        if updates.start_time is not None and updates.end_time is not None:
            if updates.is_all_day:
                patch_payload["start"] = {"date": updates.start_time.strftime("%Y-%m-%d")}
                patch_payload["end"] = {"date": updates.end_time.strftime("%Y-%m-%d")}
            else:
                patch_payload["start"] = {"dateTime": updates.start_time.isoformat()}
                patch_payload["end"] = {"dateTime": updates.end_time.isoformat()}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.patch(url, headers=headers, json=patch_payload)
            if resp.status_code != 200:
                raise ValueError(f"Failed to update Google event: HTTP {resp.status_code} - {resp.text}")
            return self._parse_google_event(resp.json(), calendar_id)

    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
        credentials: OAuthTokenBundle,
    ) -> bool:
        url = f"{self.API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events/{urllib.parse.quote(event_id)}"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.delete(url, headers=headers)
            return resp.status_code in (200, 204)

    def synchronize(
        self,
        sync_token: Optional[str],
        credentials: OAuthTokenBundle,
        calendar_id: str = "primary",
        **kwargs: Any,
    ) -> SyncResult:
        url = f"{self.API_BASE}/calendars/{urllib.parse.quote(calendar_id)}/events"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        params: Dict[str, Any] = {"singleEvents": "true"}

        if sync_token:
            params["syncToken"] = sync_token
        else:
            # Initial sync: default window past 30 days to future 90 days
            now = datetime.now(timezone.utc)
            params["timeMin"] = (now - timedelta(days=30)).isoformat()
            params["timeMax"] = (now + timedelta(days=90)).isoformat()

        synced_events: List[CalendarEventDTO] = []
        deleted_ids: List[str] = []
        new_sync_token = None

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code == 410:
                # HTTP 410 Gone: syncToken invalidated by Google
                logger.warning("Google syncToken invalidated (HTTP 410 Gone); requesting full resync.")
                return SyncResult(success=True, full_resync_required=True)
            if resp.status_code != 200:
                logger.error("Google synchronization failed: HTTP %d - %s", resp.status_code, resp.text)
                return SyncResult(success=False, error_message=f"HTTP {resp.status_code}")

            data = resp.json()
            items = data.get("items", [])
            new_sync_token = data.get("nextSyncToken")

            for item in items:
                if item.get("status") == "cancelled":
                    deleted_ids.append(item["id"])
                else:
                    synced_events.append(self._parse_google_event(item, calendar_id))

        return SyncResult(
            success=True,
            new_sync_token=new_sync_token,
            synced_events=synced_events,
            deleted_event_ids=deleted_ids,
            full_resync_required=False,
        )

    def disconnect(self, credentials: OAuthTokenBundle) -> bool:
        token_to_revoke = credentials.refresh_token or credentials.access_token
        if not token_to_revoke:
            return True
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.REVOKE_URL, params={"token": token_to_revoke})
                return resp.status_code == 200
        except Exception as e:
            logger.warning("Google token revocation network error: %s", e)
            return False

    def _parse_google_event(self, item: Dict[str, Any], calendar_id: str) -> CalendarEventDTO:
        start_obj = item.get("start", {})
        end_obj = item.get("end", {})
        is_all_day = "date" in start_obj and "dateTime" not in start_obj

        if is_all_day:
            start_time = datetime.strptime(start_obj["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_time = datetime.strptime(end_obj.get("date", start_obj["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            s_str = start_obj.get("dateTime", datetime.now(timezone.utc).isoformat())
            e_str = end_obj.get("dateTime", s_str)
            start_time = datetime.fromisoformat(s_str.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(e_str.replace("Z", "+00:00"))

        transparency = EventTransparency.OPAQUE
        if item.get("transparency") == "transparent":
            transparency = EventTransparency.TRANSPARENT

        status = EventStatus.CONFIRMED
        if item.get("status") == "tentative":
            status = EventStatus.TENTATIVE
        elif item.get("status") == "cancelled":
            status = EventStatus.CANCELLED

        # Task 2: Treat private events according to their privacy settings.
        # Do not unnecessarily capture sensitive meeting descriptions.
        visibility = item.get("visibility", "default")
        description = item.get("description")
        summary = item.get("summary") or "Untitled Meeting"
        if visibility in ("private", "confidential"):
            description = None
            if not item.get("summary"):
                summary = "Busy (Private Event)"

        # Recurrence metadata (Task 6)
        recurring_event_id = item.get("recurringEventId")
        is_recurring = bool(recurring_event_id or item.get("recurrence"))
        orig_start = None
        if "originalStartTime" in item:
            orig_obj = item["originalStartTime"]
            if "dateTime" in orig_obj:
                orig_start = datetime.fromisoformat(orig_obj["dateTime"].replace("Z", "+00:00"))
            elif "date" in orig_obj:
                orig_start = datetime.strptime(orig_obj["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Provider updated timestamp
        updated_at = None
        if "updated" in item:
            try:
                updated_at = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
            except Exception:
                pass

        tz_str = start_obj.get("timeZone") or end_obj.get("timeZone") or "UTC"

        return CalendarEventDTO(
            event_id=item.get("id", ""),
            calendar_id=calendar_id,
            provider=self.provider_id,
            title=summary,
            start_time=start_time,
            end_time=end_time,
            is_all_day=is_all_day,
            description=description,
            location_name=item.get("location"),
            status=status,
            transparency=transparency,
            organizer_email=item.get("organizer", {}).get("email"),
            attendees_count=len(item.get("attendees", [])),
            is_organizer=bool(item.get("organizer", {}).get("self", True)),
            html_link=item.get("htmlLink"),
            etag=item.get("etag"),
            timezone=tz_str,
            visibility=visibility,
            recurring_event_id=recurring_event_id,
            is_recurring=is_recurring,
            original_start_time=orig_start,
            updated_at_provider=updated_at,
            raw_payload=item,
        )
