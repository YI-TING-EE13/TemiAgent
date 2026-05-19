"""Small in-memory de-duplication cache for MQTT event ids."""

from __future__ import annotations

import time


class TTLProcessedEventCache:
    """Track recently processed event ids for a fixed time window."""

    def __init__(self, ttl_seconds: int = 600):
        """Create a cache whose entries expire after ttl_seconds."""
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, float] = {}

    def seen(self, event_id: str) -> bool:
        """Return True when the event id is currently cached."""
        self._expire()
        return event_id in self._items

    def mark_seen(self, event_id: str) -> None:
        """Record an event id as processed."""
        self._expire()
        self._items[event_id] = time.monotonic() + self.ttl_seconds

    def _expire(self) -> None:
        """Remove expired event ids."""
        now = time.monotonic()
        expired = [event_id for event_id, expires_at in self._items.items() if expires_at <= now]
        for event_id in expired:
            del self._items[event_id]
