import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Optional


class TTLCache:
    """Small in-memory LRU+TTL cache, used to avoid re-rendering a page
    with a full browser on every repeat request for the same URL.

    In-memory is sufficient here: the service runs as a single process, so
    there's no need for a shared store like Redis.
    """

    def __init__(self, ttl_seconds: float, max_size: int = 256, *, clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._clock = clock
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._store[key]
                return None

            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        if self.ttl_seconds <= 0:
            return

        with self._lock:
            self._store[key] = (self._clock() + self.ttl_seconds, value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)
