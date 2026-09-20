"""
generator/memory/event_store.py
---------------------------------
Thread-safe in-memory store for generated complaint events.
Enforces a 30-minute rolling TTL — events older than 30 min are automatically
purged so the store never grows unbounded.
"""

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

_TTL_MINUTES = 30


class EventStore:
    """
    Simple in-memory event store with 30-minute TTL.
    Thread-safe for use with Streamlit background generation.
    """

    def __init__(self, ttl_minutes: int = _TTL_MINUTES):
        self._ttl_minutes = ttl_minutes
        self._events: deque = deque()
        self._lock = threading.Lock()

    # -- Write ------------------------------------------------------

    def add_events(self, events: list[dict]) -> None:
        """Append a batch of events and purge expired ones."""
        now = datetime.now(tz=timezone.utc)
        with self._lock:
            for ev in events:
                ev["_stored_at"] = now.isoformat()
                self._events.append(ev)
            self._purge_expired(now)

    # -- Read -------------------------------------------------------

    def get_all(self) -> list[dict]:
        """Return all non-expired events (newest last)."""
        now = datetime.now(tz=timezone.utc)
        with self._lock:
            self._purge_expired(now)
            return list(self._events)

    def get_latest(self, n: int = 20) -> list[dict]:
        """Return the N most recently stored events."""
        return self.get_all()[-n:]

    def count(self) -> int:
        return len(self.get_all())

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    # -- Internal ---------------------------------------------------

    def _purge_expired(self, now: datetime) -> None:
        """Remove events older than TTL from the left (oldest) end of deque."""
        cutoff = now.timestamp() - (self._ttl_minutes * 60)
        while self._events:
            oldest = self._events[0]
            stored_at_str = oldest.get("_stored_at", "")
            try:
                stored_ts = datetime.fromisoformat(stored_at_str).timestamp()
                if stored_ts < cutoff:
                    self._events.popleft()
                else:
                    break
            except Exception:
                self._events.popleft()


# Module-level singleton shared across Streamlit reruns via st.session_state
_global_store: Optional[EventStore] = None


def get_store() -> EventStore:
    """Return (or create) the module-level singleton EventStore."""
    global _global_store
    if _global_store is None:
        _global_store = EventStore(ttl_minutes=_TTL_MINUTES)
    return _global_store
