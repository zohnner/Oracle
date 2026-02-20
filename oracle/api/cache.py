"""
api/cache.py — lightweight in-memory TTL cache.
Prevents hammering external APIs when multiple requests arrive quickly.
"""
import time
import threading
from typing import Any, Optional
from api.logger import get_logger

log = get_logger("cache")


class TTLCache:
    """Thread-safe key-value cache with per-entry expiry."""

    def __init__(self, default_ttl: int = 60):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock  = threading.Lock()
        self._ttl   = default_ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                log.debug("Cache MISS (expired): %s", key)
                return None
            log.debug("Cache HIT: %s", key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._ttl
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)
            log.debug("Cache SET: %s (ttl=%ds)", key, ttl)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
