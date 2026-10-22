"""A small in-process sliding-window limit per token for costly requests.

The counters live in the API process memory: they reset on restart and are
not shared between several API processes. That is enough for one local
server; a shared store (for example Redis) is needed behind a load balancer.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    """Allow at most `limit` events per key within `window_seconds`."""

    def __init__(
        self,
        limit: Callable[[], int],
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """limit is read on every check, so a settings change applies at once."""
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._events: dict[object, deque[float]] = {}
        # FastAPI runs synchronous routes in a thread pool.
        self._lock = threading.Lock()

    def check(self, key: object) -> int | None:
        """Record an event, or return whole seconds to wait if over the limit."""
        now = self._clock()
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - self._window:
                events.popleft()
            if len(events) >= self._limit():
                return max(1, math.ceil(events[0] + self._window - now))
            events.append(now)
            return None

    def reset(self) -> None:
        """Forget all counters (used by tests)."""
        with self._lock:
            self._events.clear()
