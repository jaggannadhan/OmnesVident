"""
rate_limiter.py — Per-API-key token-bucket rate limiter.

Sliding token bucket, in-process state. Each key gets `capacity` tokens that
refill at a steady rate. Each request consumes one token; if no tokens are
available, the request is rejected.

For Cloud Run, each container instance maintains its own bucket. With low-RPS
public APIs and our default of 5/min, this is approximate but acceptable —
two instances effectively give a user 10/min. To make it strict, swap the
backing store for Redis or Firestore — the `acquire()` interface stays the same.

Defaults are tunable via env vars:
    PUBLIC_API_RATE_PER_MIN  (default 5)

Special cases:
    * access_level == "super-user"   → bypass entirely
    * user.rate_limit_per_min == 0   → bypass (custom unlimited)
    * user.rate_limit_per_min > 0    → that user's specific cap
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

DEFAULT_RATE_PER_MIN = int(os.getenv("PUBLIC_API_RATE_PER_MIN", "5"))


@dataclass
class _Bucket:
    capacity:    float   # max tokens
    tokens:      float   # current tokens
    refill_rate: float   # tokens added per second
    last_refill: float   # monotonic timestamp of last refill


class RateLimiter:
    """Thread-safe in-process token-bucket rate limiter, keyed by string."""

    def __init__(self) -> None:
        self._buckets: Dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, key: str, rate_per_min: int) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is not None and bucket.capacity == rate_per_min:
            return bucket
        # New bucket OR a tier change → re-init
        bucket = _Bucket(
            capacity=float(rate_per_min),
            tokens=float(rate_per_min),
            refill_rate=rate_per_min / 60.0,
            last_refill=time.monotonic(),
        )
        self._buckets[key] = bucket
        return bucket

    def acquire(
        self,
        key: str,
        *,
        rate_per_min: Optional[int] = None,
        unlimited: bool = False,
    ) -> bool:
        """
        Attempt to consume a single token.

        Returns True on success (request allowed) or False on rejection.
        `unlimited=True` (or rate_per_min == 0) always returns True.
        """
        if unlimited or rate_per_min == 0:
            return True

        rate = rate_per_min if (rate_per_min and rate_per_min > 0) else DEFAULT_RATE_PER_MIN

        with self._lock:
            bucket = self._get_or_create(key, rate)
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                bucket.capacity,
                bucket.tokens + elapsed * bucket.refill_rate,
            )
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False

    def retry_after_seconds(self, key: str) -> int:
        """How many seconds until the bucket has at least one token. Used in 429 response."""
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.refill_rate <= 0:
                return 1
            needed = max(0.0, 1.0 - bucket.tokens)
            return max(1, int(needed / bucket.refill_rate) + 1)


# Module-level singleton — every request handler shares the same buckets.
limiter = RateLimiter()
