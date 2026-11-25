"""Abstract base calendar provider defining common calendar integration interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from integrations.app.schemas.integration_schemas import (
    CalendarDTO,
    CalendarEventCreateDTO,
    CalendarEventDTO,
    CalendarEventUpdateDTO,
    OAuthTokenBundle,
    SyncResult,
)


class BaseCalendarProvider(ABC):
    """Unified calendar provider interface.

    Every provider (Google Calendar, Microsoft Outlook, etc.) implements this
    contract without leaking provider-specific client logic into ContextIQ core.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'google_calendar', 'microsoft_outlook')."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        pass

    @property
    @abstractmethod
    def default_scopes(self) -> List[str]:
        """Minimal read-only scopes requested by default."""
        pass

    @property
    @abstractmethod
    def write_scopes(self) -> List[str]:
        """Extended write scopes requested only when two-way sync is enabled."""
        pass

    @abstractmethod
    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        code_challenge: Optional[str] = None,
        request_write_access: bool = False,
    ) -> str:
        """Generate provider OAuth authorization consent URL."""
        pass

    @abstractmethod
    def authenticate(
        self,
        auth_code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
        **kwargs: Any,
    ) -> OAuthTokenBundle:
        """Exchange authorization code for an OAuth access and refresh token bundle."""
        pass

    @abstractmethod
    def refresh_credentials(self, refresh_token: str) -> OAuthTokenBundle:
        """Refresh expired credentials using the refresh token."""
        pass

    @abstractmethod
    def list_calendars(self, credentials: OAuthTokenBundle) -> List[CalendarDTO]:
        """List user calendars available under this account."""
        pass

    @abstractmethod
    def list_events(
        self,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime,
        credentials: OAuthTokenBundle,
    ) -> List[CalendarEventDTO]:
        """List calendar events within a specified time interval."""
        pass

    @abstractmethod
    def get_event(
        self,
        calendar_id: str,
        event_id: str,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        """Retrieve a single calendar event by ID."""
        pass

    @abstractmethod
    def create_event(
        self,
        calendar_id: str,
        event: CalendarEventCreateDTO,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        """Create a new event in the user's external calendar."""
        pass

    @abstractmethod
    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: CalendarEventUpdateDTO,
        credentials: OAuthTokenBundle,
    ) -> CalendarEventDTO:
        """Update an existing event in the user's external calendar."""
        pass

    @abstractmethod
    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
        credentials: OAuthTokenBundle,
    ) -> bool:
        """Delete an event from the user's external calendar."""
        pass

    @abstractmethod
    def synchronize(
        self,
        sync_token: Optional[str],
        credentials: OAuthTokenBundle,
        calendar_id: str = "primary",
        **kwargs: Any,
    ) -> SyncResult:
        """Perform initial or incremental delta synchronization."""
        pass

    @abstractmethod
    def disconnect(self, credentials: OAuthTokenBundle) -> bool:
        """Revoke user access grant remotely on the provider identity system."""
        pass
