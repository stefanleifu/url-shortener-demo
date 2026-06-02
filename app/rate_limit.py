from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")

        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> RateLimitResult:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._requests[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = math.ceil(bucket[0] + self.window_seconds - now)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=max(1, retry_after),
                )

            bucket.append(now)
            return RateLimitResult(
                allowed=True,
                remaining=self.limit - len(bucket),
                retry_after_seconds=0,
            )
