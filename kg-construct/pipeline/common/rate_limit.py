"""Async rate limiting helpers for worker-local API calls."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RateLimitSnapshot:
    max_calls: int
    window_seconds: float
    total_acquires: int
    wait_events: int
    total_wait_seconds: float


class AsyncSlidingWindowRateLimiter:
    """Worker-local sliding-window limiter for outbound API calls."""

    def __init__(self, max_calls: int, *, window_seconds: float = 60.0) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.max_calls = max_calls
        self.window_seconds = float(window_seconds)
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()
        self._total_acquires = 0
        self._wait_events = 0
        self._total_wait_seconds = 0.0

    async def acquire(self) -> float:
        total_wait = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self.window_seconds:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    self._total_acquires += 1
                    if total_wait > 0:
                        self._wait_events += 1
                        self._total_wait_seconds += total_wait
                    return total_wait

                oldest = self._timestamps[0]
                sleep_for = max(self.window_seconds - (now - oldest), 0.001)

            await asyncio.sleep(sleep_for)
            total_wait += sleep_for

    def snapshot(self) -> RateLimitSnapshot:
        return RateLimitSnapshot(
            max_calls=self.max_calls,
            window_seconds=self.window_seconds,
            total_acquires=self._total_acquires,
            wait_events=self._wait_events,
            total_wait_seconds=self._total_wait_seconds,
        )
