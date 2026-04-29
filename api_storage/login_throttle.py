"""
login_throttle.py — Per-email failed-login throttling.

Slows credential-stuffing attacks by tracking failed `/v1/auth/login`
attempts per email and forcing a cooldown after `MAX_FAILS` strikes
within `WINDOW_SECONDS`. Successful logins reset the counter for that
email.

Storage is in-process memory — same trade-offs as `rate_limiter.py`:
each Cloud Run instance keeps its own ledger. For low-traffic auth
this is fine; if we ever scale horizontally enough that an attacker
could meaningfully spread their failed attempts across instances,
swap the dict for Redis or Firestore behind the same interface.

We deliberately track failures for *all* emails — including ones that
don't exist in the user table — so a 429 cannot be used to enumerate
which emails are registered.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Dict, List

WINDOW_SECONDS = int(os.getenv("LOGIN_FAIL_WINDOW_SEC", "900"))   # 15 min default
MAX_FAILS      = int(os.getenv("LOGIN_FAIL_MAX",        "5"))     # strikes per window

# email_lc -> list of monotonic timestamps of failed attempts within the window
_failures: Dict[str, List[float]] = {}
_lock = threading.Lock()


def _key(email: str) -> str:
    return email.strip().lower()


def _trim(timestamps: List[float], now: float) -> List[float]:
    cutoff = now - WINDOW_SECONDS
    return [t for t in timestamps if t > cutoff]


def check_login_allowed(email: str) -> int:
    """
    Inspect the failure ledger for `email`.

    Returns 0 when the attempt may proceed. Returns a positive integer
    (seconds until the oldest in-window failure expires) when the
    cooldown is active and the caller should respond 429.
    """
    k = _key(email)
    now = time.monotonic()
    with _lock:
        ts = _trim(_failures.get(k, []), now)
        if len(ts) >= MAX_FAILS:
            oldest = ts[0]
            return max(1, int(oldest + WINDOW_SECONDS - now) + 1)
        _failures[k] = ts
        return 0


def record_failure(email: str) -> None:
    k = _key(email)
    now = time.monotonic()
    with _lock:
        ts = _trim(_failures.get(k, []), now)
        ts.append(now)
        _failures[k] = ts


def record_success(email: str) -> None:
    """Clear the failure ledger for this email — they got the password right."""
    k = _key(email)
    with _lock:
        _failures.pop(k, None)


def reset_all() -> None:
    """Test helper — clear all failure counters."""
    with _lock:
        _failures.clear()
