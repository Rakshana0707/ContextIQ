"""Thread-safe event queue for in-memory event buffering."""
import logging
import queue
from typing import Any

logger = logging.getLogger(__name__)


class EventQueue:
    """Thread-safe queue with max capacity enforcement."""

    def __init__(self, max_size: int = 1000):
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=max_size)

    def put(self, event: dict[str, Any], block: bool = False, timeout: float | None = None) -> bool:
        """Enqueue an event. Drops oldest or rejects if full."""
        try:
            self._queue.put(event, block=block, timeout=timeout)
            return True
        except queue.Full:
            logger.warning("Event queue full (%d items); dropping event %s", self._queue.maxsize, event.get("event_type"))
            return False

    def get_batch(self, max_items: int = 50) -> list[dict[str, Any]]:
        """Drain up to max_items events from the queue without blocking."""
        items: list[dict[str, Any]] = []
        while len(items) < max_items:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def qsize(self) -> int:
        """Return approximate number of items currently in queue."""
        return self._queue.qsize()

    def is_empty(self) -> bool:
        """Return True if queue is empty."""
        return self._queue.empty()

    def clear(self) -> None:
        """Discard all pending in-memory events."""
        with self._queue.mutex:
            self._queue.queue.clear()
