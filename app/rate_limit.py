import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from app.errors import ScrapeError


class RateLimiter:
    """In-memory sliding-window rate limiter, keyed by an arbitrary string
    (typically the caller's IP address).

    In-memory is sufficient here: the service runs as a single process, so
    there's no need for a shared store like Redis to coordinate across
    workers.
    """

    def __init__(self, max_requests: int, window_seconds: float, *, clock: Callable[[], float] = time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()

            if len(hits) >= self.max_requests:
                return False

            hits.append(now)
            return True


def assert_api_key(*, provided: str | None, expected: str | None) -> None:
    """No-op when no API key is configured (open access, the default).
    When one is configured, the caller must present the exact match."""
    if expected is None:
        return
    if not provided or provided != expected:
        raise ScrapeError(401, "Invalid or missing API key.")
