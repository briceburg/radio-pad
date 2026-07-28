from __future__ import annotations

import time
from collections.abc import Callable
from threading import RLock

from cachetools import TTLCache


class ExpiringCache[Key, Value]:
    """Small process-local cache for datastore-backed values."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int = 128,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._entries: TTLCache[Key, Value] = TTLCache(maxsize=max_entries, ttl=ttl_seconds, timer=clock)
        self._lock = RLock()

    def get_or_load(self, key: Key, load: Callable[[], Value]) -> Value:
        if self._ttl_seconds == 0:
            return load()

        with self._lock:
            try:
                return self._entries[key]
            except KeyError:
                value = load()
                self._entries[key] = value
                return value

    def invalidate(self, key: Key) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
