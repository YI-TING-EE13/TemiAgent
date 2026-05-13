from __future__ import annotations

import time


class TTLProcessedEventCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, float] = {}

    def seen(self, event_id: str) -> bool:
        self._expire()
        return event_id in self._items

    def mark_seen(self, event_id: str) -> None:
        self._expire()
        self._items[event_id] = time.monotonic() + self.ttl_seconds

    def _expire(self) -> None:
        now = time.monotonic()
        expired = [event_id for event_id, expires_at in self._items.items() if expires_at <= now]
        for event_id in expired:
            del self._items[event_id]
