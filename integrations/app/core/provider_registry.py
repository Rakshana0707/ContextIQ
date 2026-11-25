"""Provider registry and factory for calendar integrations."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from integrations.app.providers.base_calendar_provider import BaseCalendarProvider
from integrations.app.providers.google.google_calendar_provider import GoogleCalendarProvider
from integrations.app.providers.microsoft.microsoft_outlook_provider import MicrosoftOutlookProvider

logger = logging.getLogger(__name__)


class UnsupportedProviderError(Exception):
    """Raised when an unrecognized provider key is requested."""
    pass


class ProviderRegistry:
    """Thread-safe registry for calendar integration providers."""

    _providers: Dict[str, Type[BaseCalendarProvider]] = {}
    _instances: Dict[str, BaseCalendarProvider] = {}

    @classmethod
    def register(cls, provider_id: str, provider_cls: Type[BaseCalendarProvider]) -> None:
        """Register a calendar provider class."""
        cls._providers[provider_id] = provider_cls
        logger.debug("Registered integration provider: %s", provider_id)

    @classmethod
    def get_provider(
        cls,
        provider_id: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> BaseCalendarProvider:
        """Get or instantiate a provider adapter by provider_id."""
        if provider_id not in cls._providers:
            raise UnsupportedProviderError(
                f"Provider '{provider_id}' is not supported. Supported: {cls.list_providers()}"
            )

        # If specific credentials are provided, return fresh instance
        if client_id is not None or client_secret is not None:
            return cls._providers[provider_id](
                client_id=client_id or "default-client-id",
                client_secret=client_secret or "default-client-secret",
            )

        if provider_id not in cls._instances:
            cls._instances[provider_id] = cls._providers[provider_id]()

        return cls._instances[provider_id]

    @classmethod
    def list_providers(cls) -> List[str]:
        """List registered provider IDs."""
        return list(cls._providers.keys())


# Pre-register built-in providers
ProviderRegistry.register("google_calendar", GoogleCalendarProvider)
ProviderRegistry.register("microsoft_outlook", MicrosoftOutlookProvider)
