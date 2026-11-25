"""
Reliability Engineering Circuit Breakers (ContextIQ Phase 7.8).
Protects external calendar, notification, and desktop agent integrations
from cascading failures during provider outages.
"""
from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from app.core.metrics import metrics_registry

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"        # Normal operation: requests pass through
    OPEN = "OPEN"            # Provider tripped: fail fast without calling provider
    HALF_OPEN = "HALF_OPEN"  # Testing recovery: probe with limited requests


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is rejected by an open circuit breaker."""
    pass


class CircuitBreaker:
    """Thread-safe circuit breaker with bounded failure thresholds and automatic cool-down."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 2,
        half_open_success_threshold: Optional[int] = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_calls = (
            half_open_success_threshold
            if half_open_success_threshold is not None
            else half_open_max_calls
        )

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._consecutive_success_count = 0
        self._last_state_change = time.time()
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            # Check if timeout has expired to transition OPEN -> HALF_OPEN
            if self._state == CircuitBreakerState.OPEN:
                if (time.time() - self._last_state_change) >= self.recovery_timeout_seconds:
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0
                    self._last_state_change = time.time()
                    logger.info(f"Circuit breaker '{self.name}' entered HALF_OPEN state.")
            return self._state

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Executes the callable guarded by the circuit breaker."""
        current_state = self.state

        if current_state == CircuitBreakerState.OPEN:
            metrics_registry.record_circuit_breaker_trip()
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Provider call rejected to prevent cascading failure."
            )

        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN and reached probe limit."
                    )
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._consecutive_success_count += 1
                if self._consecutive_success_count >= self.half_open_max_calls:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    self._consecutive_success_count = 0
                    self._last_state_change = time.time()
                    logger.info(f"Circuit breaker '{self.name}' recovered to CLOSED.")
            else:
                self._failure_count = 0

    def _on_failure(self, error: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            logger.warning(
                f"Circuit breaker '{self.name}' failure {self._failure_count}/{self.failure_threshold}: {error}"
            )
            if self._state == CircuitBreakerState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                self._last_state_change = time.time()
                metrics_registry.record_circuit_breaker_trip()
                logger.error(f"Circuit breaker '{self.name}' TRIPPED to OPEN state!")

    def reset(self) -> None:
        """Manually forces the breaker back to CLOSED state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._consecutive_success_count = 0
            self._last_state_change = time.time()

    def trip(self) -> None:
        """Manually forces the breaker to OPEN state (for maintenance / test)."""
        with self._lock:
            self._state = CircuitBreakerState.OPEN
            self._last_state_change = time.time()
            metrics_registry.record_circuit_breaker_trip()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
                "last_state_change": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._last_state_change)
                ),
            }


class CircuitBreakerRegistry:
    """Manages all system circuit breakers."""

    _breakers: Dict[str, CircuitBreaker] = {}
    _lock = threading.Lock()

    @classmethod
    def get_or_create(
        cls,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
    ) -> CircuitBreaker:
        with cls._lock:
            if name not in cls._breakers:
                cls._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout_seconds=recovery_timeout_seconds,
                )
            return cls._breakers[name]

    @classmethod
    def list_statuses(cls) -> List[Dict[str, Any]]:
        with cls._lock:
            return [b.get_status() for b in cls._breakers.values()]


# Pre-register critical integration circuit breakers
circuit_breaker_registry = CircuitBreakerRegistry()
circuit_breaker_registry.get_or_create("google_calendar", failure_threshold=4, recovery_timeout_seconds=20.0)
circuit_breaker_registry.get_or_create("microsoft_calendar", failure_threshold=4, recovery_timeout_seconds=20.0)
circuit_breaker_registry.get_or_create("notification_delivery", failure_threshold=5, recovery_timeout_seconds=15.0)
