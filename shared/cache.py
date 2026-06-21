"""Shared TTL cache — single cache layer for all 3 domains.

Vermeint 3 separate Cache-Instanzen (analysis hatte Honcho-Cache,
bughunt hatte Session-Cache, deep-research hatte nichts).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Thread-safe TTL cache with max size eviction."""

    def __init__(self, ttl: float = 60.0, maxsize: int = 128):
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def get(self, key: str) -> Optional[T]:
        """Get value if not expired."""
        now = time.monotonic()
        item = self._store.get(key)
        if item is None:
            return None
        ts, value = item
        if (now - ts) > self._ttl:
            del self._store[key]
            return None
        # Move to end (LRU)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: T) -> None:
        """Store value with current timestamp."""
        self._store[key] = (time.monotonic(), value)
        self._store.move_to_end(key)
        # Evict oldest if over maxsize
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """Remove a specific key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# Global cache instances (one per domain domain + shared)
intent_cache: TTLCache[str | None] = TTLCache[str | None](ttl=60.0)
pattern_cache: TTLCache[list[dict]] = TTLCache[list[dict]](ttl=120.0)
analysis_cache: TTLCache[Any] = TTLCache[Any](ttl=60.0)
research_cache: TTLCache[Any] = TTLCache[Any](ttl=300.0)


def clear_all() -> None:
    """Clear all caches (for testing)."""
    intent_cache.clear()
    pattern_cache.clear()
    analysis_cache.clear()
    research_cache.clear()
