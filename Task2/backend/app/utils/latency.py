"""
Latency instrumentation and rolling statistics.
Maintains a fixed-size window of recent query latencies
for live P50/P70/P100 readout in the UI.
"""

import time
from collections import deque
from contextlib import contextmanager

import numpy as np

from app.models import LatencyStats


class LatencyTracker:
    """Rolling window of query latencies for live stats."""

    def __init__(self, window_size: int = 500):
        self._window: deque[float] = deque(maxlen=window_size)

    def record(self, latency_ms: float):
        self._window.append(latency_ms)

    def stats(self) -> LatencyStats:
        if not self._window:
            return LatencyStats()
        arr = np.array(self._window)
        return LatencyStats(
            p50_ms=round(float(np.percentile(arr, 50)), 1),
            p70_ms=round(float(np.percentile(arr, 70)), 1),
            p100_ms=round(float(np.max(arr)), 1),
            query_count=len(self._window),
        )


@contextmanager
def timed_ms():
    """Context manager that yields a dict; on exit, populates 'ms' key."""
    result = {"ms": 0.0}
    t0 = time.perf_counter()
    try:
        yield result
    finally:
        result["ms"] = round((time.perf_counter() - t0) * 1000, 2)


# Global tracker instance
latency_tracker = LatencyTracker()
