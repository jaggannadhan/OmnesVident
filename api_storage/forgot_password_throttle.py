"""
forgot_password_throttle.py — Per-email throttle for `/v1/auth/forgot-password`.

Same in-memory-deque pattern as `login_throttle.py` but separate state so a
user being throttled on login attempts doesn't also block their reset-email
requests (and vice versa).

Default: 3 reset-email requests per email every 15 minutes. Tunable via:
    FORGOT_PW_MAX            (default 3)
    FORGOT_PW_WINDOW_SEC     (default 900)
"""

from __future__ import annotations

import os
import threading
import time
from typing import Dict, List

WINDOW_SECONDS = int(os.getenv("FORGOT_PW_WINDOW_SEC", "900"))
MAX_REQUESTS   = int(os.getenv("FORGOT_PW_MAX",        "3"))

_attempts: Dict[str, List[float]] = {}
_lock = threading.Lock()


def _key(email: str) -> str:
    return email.strip().lower()


def _trim(timestamps: List[float], now: float) -> List[float]:
    cutoff = now - WINDOW_SECONDS
    return [t for t in timestamps if t > cutoff]


def check_allowed(email: str) -> int:
    """
    Returns 0 when the request may proceed, otherwise the seconds until the
    oldest in-window request expires.
    """
    k = _key(email)
    now = time.monotonic()
    with _lock:
        ts = _trim(_attempts.get(k, []), now)
        if len(ts) >= MAX_REQUESTS:
            oldest = ts[0]
            return max(1, int(oldest + WINDOW_SECONDS - now) + 1)
        _attempts[k] = ts
        return 0


def record(email: str) -> None:
    """Record a successful (or attempted) forgot-password request."""
    k = _key(email)
    now = time.monotonic()
    with _lock:
        ts = _trim(_attempts.get(k, []), now)
        ts.append(now)
        _attempts[k] = ts


def reset_all() -> None:
    """Test helper — clear all counters."""
    with _lock:
        _attempts.clear()
