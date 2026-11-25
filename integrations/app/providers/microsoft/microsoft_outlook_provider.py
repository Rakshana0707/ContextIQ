"""Microsoft Outlook (Microsoft Graph) calendar provider adapter."""
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


class MicrosoftOutlookProvider(BaseCalendarProvider):
    """Microsoft Outlook / Microsoft 365 implementation of BaseCalendarProvider."""

    AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        client_id: str = "microsoft-client-id-placeholder",
        client_secret: str = "microsoft-client-secret-placeholder",
        timeout: float = 10.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout

    @property
    def provider_id(self) -> str:
        return "microsoft_outlook"

    @property
    def provider_name(self) -> str:
        return "Microsoft Outlook"

    @property
    def default_scopes(self) -> List[str]:
        return ["Calendars.Read", "User.Read", "offline_access"]

    @property
    def write_scopes(self) -> List[str]:
        return ["Calendars.ReadWrite", "User.Read", "offline_access"]

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
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": " ".join(scopes),
            "state": state,
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
                logger.error("Microsoft OAuth exchange failed: status=%d, body=%s", resp.status_code, redact_secret(resp.text))
                raise ValueError(f"Microsoft authentication failed: HTTP {resp.status_code}")
            data = resp.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        granted_scope = data.get("scope", "").split(" ") if data.get("scope") else self.default_scopes

        # Retrieve user email/id from Microsoft Graph /me
        provider_email = None
        provider_user_id = None
        access_token = data["access_token"]
        try:
            with httpx.Client(timeout=self.timeout) as client:
                me_resp = client.get(
                    f"{self.GRAPH_BASE}/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    provider_email = me_data.get("mail") or me_data.get("userPrincipalName")
                    provider_user_id = me_data.get("id")
        except Exception as e:
            logger.debug("Failed to retrieve Microsoft profile: %s", e)

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
                logger.error("Microsoft token refresh failed: status=%d, body=%s", resp.status_code, redact_secret(resp.text))
                raise ValueError(f"Microsoft token refresh failed: HTTP {resp.status_code}")
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
        url = f"{self.GRAPH_BASE}/me/calendars"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        calendars: List[CalendarDTO] = []

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error("Microsoft list_calendars failed: HTTP %d", resp.status_code)
                return []
            items = resp.json().get("value", [])
            for item in items:
                calendars.append(
                    CalendarDTO(
                        calendar_id=item.get("id", "primary"),
                        name=item.get("name", "Calendar"),
                        is_primary=bool(item.get("isDefaultCalendar", False)),
                        access_role=item.get("canEdit", False) and "writer" or "reader",
                        time_zone=item.get("defaultOnlineMeetingProvider"),
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
        url = f"{self.GRAPH_BASE}/me/calendarView"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        params = {
            "startDateTime": start_time.isoformat(),
            "endDateTime": end_time.isoformat(),
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.error("Microsoft list_events failed: HTTP %d", resp.status_code)
                return []
            items = resp.json().get("value", [])
            return [self._parse_microsoft_event(item, calendar_id) for item in items]

    def get_event(
        self,
        calendar_id: str,
        event_id: str,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        url = f"{self.GRAPH_BASE}/me/events/{urllib.parse.quote(event_id)}"
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Microsoft event not found: HTTP {resp.status_code}")
            return self._parse_microsoft_event(resp.json(), calendar_id)

    def create_event(
        self,
        calendar_id: str,
        event: CalendarEventCreateDTO,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        url = f"{self.GRAPH_BASE}/me/calendars/{urllib.parse.quote(calendar_id)}/events"
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "subject": event.title,
            "body": {"contentType": "text", "content": event.description or ""},
            "location": {"displayName": event.location_name or ""},
            "isAllDay": event.is_all_day,
            "showAs": "busy" if event.transparency == EventTransparency.OPAQUE else "free",
            "start": {"dateTime": event.start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": event.end_time.isoformat(), "timeZone": "UTC"},
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                raise ValueError(f"Failed to create Microsoft event: HTTP {resp.status_code} - {resp.text}")
            return self._parse_microsoft_event(resp.json(), calendar_id)

    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: CalendarEventUpdateDTO,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        url = f"{self.GRAPH_BASE}/me/events/{urllib.parse.quote(event_id)}"
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {}
        if updates.title is not None:
            payload["subject"] = updates.title
        if updates.description is not None:
            payload["body"] = {"contentType": "text", "content": updates.description}
        if updates.location_name is not None:
            payload["location"] = {"displayName": updates.location_name}
        if updates.is_all_day is not None:
            payload["isAllDay"] = updates.is_all_day
        if updates.transparency is not None:
            payload["showAs"] = "busy" if updates.transparency == EventTransparency.OPAQUE else "free"
        if updates.start_time is not None and updates.end_time is not None:
            payload["start"] = {"dateTime": updates.start_time.isoformat(), "timeZone": "UTC"}
            payload["end"] = {"dateTime": updates.end_time.isoformat(), "timeZone": "UTC"}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.patch(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise ValueError(f"Failed to update Microsoft event: HTTP {resp.status_code} - {resp.text}")
            return self._parse_microsoft_event(resp.json(), calendar_id)

    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
        credentials: OAuthTokenBundle,
    ) -> bool:
        url = f"{self.GRAPH_BASE}/me/events/{urllib.parse.quote(event_id)}"
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
        headers = {"Authorization": f"Bearer {credentials.access_token}"}
        synced_events: List[CalendarEventDTO] = []
        deleted_ids: List[str] = []
        new_sync_token = None

        if sync_token and sync_token.startswith("http"):
            current_url = sync_token
            params: Dict[str, Any] = {}
        else:
            if calendar_id and calendar_id != "primary":
                current_url = f"{self.GRAPH_BASE}/me/calendars/{urllib.parse.quote(calendar_id)}/calendarView/delta"
            else:
                current_url = f"{self.GRAPH_BASE}/me/calendarView/delta"
            now = datetime.now(timezone.utc)
            params = {
                "startDateTime": (now - timedelta(days=30)).isoformat(),
                "endDateTime": (now + timedelta(days=90)).isoformat(),
            }

        max_pages = 50
        page_count = 0

        with httpx.Client(timeout=self.timeout) as client:
            while current_url and page_count < max_pages:
                page_count += 1
                # When using nextLink, parameters are already embedded in the URL
                use_params = params if page_count == 1 and not (sync_token and sync_token.startswith("http")) else None
                resp = client.get(current_url, headers=headers, params=use_params)

                if resp.status_code in (404, 410):
                    logger.warning("Microsoft deltaToken invalidated (HTTP %d); requesting full resync.", resp.status_code)
                    return SyncResult(success=True, full_resync_required=True)

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "5")
                    logger.warning("Microsoft Graph API throttled (HTTP 429), Retry-After: %s", retry_after)
                    return SyncResult(success=False, error_message=f"Throttled by Microsoft Graph (Retry-After: {retry_after}s)")

                if resp.status_code != 200:
                    logger.error("Microsoft delta sync failed: HTTP %d - %s", resp.status_code, resp.text)
                    return SyncResult(success=False, error_message=f"HTTP {resp.status_code}")

                data = resp.json()

                # Check if Graph signaled resyncRequired inside body
                if "error" in data and data.get("error", {}).get("code") in ("resyncRequired", "syncStateInvalid"):
                    logger.warning("Microsoft Graph error indicated resyncRequired; requesting full resync.")
                    return SyncResult(success=True, full_resync_required=True)

                items = data.get("value", [])
                for item in items:
                    if "@removed" in item:
                        deleted_ids.append(item["id"])
                    else:
                        synced_events.append(self._parse_microsoft_event(item, calendar_id))

                # Check for nextLink pagination vs final deltaLink
                next_link = data.get("@odata.nextLink")
                delta_link = data.get("@odata.deltaLink")

                if delta_link:
                    new_sync_token = delta_link

                current_url = next_link

        return SyncResult(
            success=True,
            new_sync_token=new_sync_token or sync_token,
            synced_events=synced_events,
            deleted_event_ids=deleted_ids,
            full_resync_required=False,
        )

    def disconnect(self, credentials: OAuthTokenBundle) -> bool:
        # Microsoft tokens are invalidated through sign-out sessions or local revocation
        return True

    def _parse_microsoft_event(self, item: Dict[str, Any], calendar_id: str) -> CalendarEventDTO:
        start_obj = item.get("start", {})
        end_obj = item.get("end", {})
        s_str = start_obj.get("dateTime", datetime.now(timezone.utc).isoformat())
        e_str = end_obj.get("dateTime", s_str)

        try:
            start_time = datetime.fromisoformat(s_str.replace("Z", "+00:00"))
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
        except Exception:
            start_time = datetime.now(timezone.utc)

        try:
            end_time = datetime.fromisoformat(e_str.replace("Z", "+00:00"))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
        except Exception:
            end_time = datetime.now(timezone.utc)

        transparency = EventTransparency.OPAQUE
        if item.get("showAs") in ("free", "tentative"):
            transparency = EventTransparency.TRANSPARENT

        status = EventStatus.CONFIRMED
        if item.get("isCancelled"):
            status = EventStatus.CANCELLED

        # Task 3: Sensitivity and Privacy Invariant
        # Microsoft Graph sensitivities: "normal", "personal", "private", "confidential"
        sensitivity = item.get("sensitivity", "normal")
        is_private = sensitivity in ("private", "confidential")
        summary = item.get("subject") or "Untitled Meeting"
        body_content = item.get("body", {}).get("content")
        if is_private:
            body_content = None
            if not item.get("subject"):
                summary = "Busy (Private Event)"

        # Task 6: Recurrence & Occurrences
        series_master_id = item.get("seriesMasterId")
        evt_type = item.get("type", "singleInstance")
        is_recurring = evt_type in ("seriesMaster", "occurrence", "exception") or bool(series_master_id) or bool(item.get("recurrence"))

        # Timezone & Modification Timestamps
        tz_str = start_obj.get("timeZone") or end_obj.get("timeZone") or "UTC"
        updated_at = None
        if "lastModifiedDateTime" in item:
            try:
                updated_at = datetime.fromisoformat(item["lastModifiedDateTime"].replace("Z", "+00:00"))
            except Exception:
                pass

        # Online meeting join URL
        online_meeting_url = item.get("onlineMeeting", {}).get("joinUrl") or item.get("onlineMeetingUrl")

        return CalendarEventDTO(
            event_id=item.get("id", ""),
            calendar_id=calendar_id,
            provider=self.provider_id,
            title=summary,
            start_time=start_time,
            end_time=end_time,
            is_all_day=bool(item.get("isAllDay", False)),
            description=body_content,
            location_name=item.get("location", {}).get("displayName"),
            status=status,
            transparency=transparency,
            organizer_email=item.get("organizer", {}).get("emailAddress", {}).get("address"),
            attendees_count=len(item.get("attendees", [])),
            is_organizer=bool(item.get("isOrganizer", True)),
            html_link=online_meeting_url or item.get("webLink"),
            etag=item.get("@odata.etag"),
            timezone=tz_str,
            visibility=sensitivity,
            recurring_event_id=series_master_id,
            is_recurring=is_recurring,
            original_start_time=start_time if series_master_id else None,
            updated_at_provider=updated_at,
            raw_payload=item,
        )
