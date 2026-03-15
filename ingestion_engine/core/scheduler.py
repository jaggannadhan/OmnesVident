"""
scheduler.py — Request Budget & Token Bucket for API Rate Limiting.

Each provider API is assigned a TokenBucket with its free-tier capacity and
reset period ("daily" or "monthly").  Before a provider makes a live request
it calls `RequestScheduler.consume(provider_name)`.  If the bucket is empty
the call returns False and the provider falls back to its backup.

State is persisted to a JSON file so budgets survive process restarts.
The file is written atomically (write-tmp → rename) to avoid corruption.

Usage:
    scheduler = RequestScheduler()
    if scheduler.consume("gnews"):
        # make live API call
    else:
        # use backup provider
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).parent / "budget_state.json"

# ---------------------------------------------------------------------------
# Default free-tier budgets
# ---------------------------------------------------------------------------
_DEFAULT_BUDGETS: Dict[str, dict] = {
    "currents":   {"capacity": 600,   "period": "monthly"},   # CURRENTS_NEW_API
    "worldnews":  {"capacity": 1500,  "period": "monthly"},   # WORLD_NEWS_API_KEY
    "mediastack": {"capacity": 500,   "period": "monthly"},   # MEDIA_STACK_NEWS_API_KEY
    "newsdata":   {"capacity": 200,   "period": "daily"},
    "newscatcher":{"capacity": 10000, "period": "monthly"},
    "gnews":      {"capacity": 100,   "period": "daily"},      # GNEWS_API
}


class TokenBucket:
    """
    Tracks consumed requests for a single API within the current period.

    Attributes:
        name:         Provider identifier (e.g. "gnews").
        capacity:     Max requests per period.
        period:       "daily" or "monthly".
        count:        Requests consumed in the current period.
        period_start: ISO date string when the current period started.
    """

    def __init__(
        self,
        name: str,
        capacity: int,
        period: str,
        count: int = 0,
        period_start: Optional[str] = None,
    ) -> None:
        self.name = name
        self.capacity = capacity
        self.period = period
        self.count = count
        self.period_start: str = period_start or self._current_period_start()

    # ------------------------------------------------------------------

    def _current_period_start(self) -> str:
        today = date.today()
        if self.period == "monthly":
            return today.replace(day=1).isoformat()
        return today.isoformat()  # daily

    def _period_expired(self) -> bool:
        return self.period_start != self._current_period_start()

    def _reset_if_expired(self) -> None:
        if self._period_expired():
            logger.info(
                "TokenBucket [%s]: period rolled over (%s → %s), resetting count %d → 0.",
                self.name, self.period_start, self._current_period_start(), self.count,
            )
            self.count = 0
            self.period_start = self._current_period_start()

    # ------------------------------------------------------------------

    def can_consume(self) -> bool:
        self._reset_if_expired()
        return self.count < self.capacity

    def consume(self) -> bool:
        """Consume one request token.  Returns True if allowed, False if exhausted."""
        self._reset_if_expired()
        if self.count < self.capacity:
            self.count += 1
            return True
        logger.warning(
            "TokenBucket [%s]: quota exhausted (%d/%d %s).",
            self.name, self.count, self.capacity, self.period,
        )
        return False

    def remaining(self) -> int:
        self._reset_if_expired()
        return max(0, self.capacity - self.count)

    def to_dict(self) -> dict:
        return {
            "capacity":     self.capacity,
            "period":       self.period,
            "count":        self.count,
            "period_start": self.period_start,
        }


class RequestScheduler:
    """
    Central rate-limit controller.

    One shared instance should be created in main.py and passed to every
    provider that needs budget awareness (via ProviderFactory).

    Thread safety: not needed — the ingestion engine is single-threaded
    async; all writes happen in the same event-loop iteration.
    """

    def __init__(self, state_file: Optional[Path] = None) -> None:
        self._state_file = state_file or _STATE_FILE
        self._buckets: Dict[str, TokenBucket] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence

    def _load(self) -> None:
        state: dict = {}
        if self._state_file.exists():
            try:
                with open(self._state_file, encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("RequestScheduler: could not load state — %s", exc)

        for name, defaults in _DEFAULT_BUDGETS.items():
            saved = state.get(name, {})
            self._buckets[name] = TokenBucket(
                name=name,
                capacity=saved.get("capacity", defaults["capacity"]),
                period=saved.get("period", defaults["period"]),
                count=saved.get("count", 0),
                period_start=saved.get("period_start"),
            )

        logger.info(
            "RequestScheduler: loaded budgets for %s.",
            ", ".join(
                f"{n}({b.remaining()}/{b.capacity} {b.period})"
                for n, b in self._buckets.items()
            ),
        )

    def save(self) -> None:
        """Persist current bucket counts to disk (atomic write)."""
        data = {name: bucket.to_dict() for name, bucket in self._buckets.items()}
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self._state_file.parent, suffix=".tmp", prefix="budget_"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._state_file)
        except OSError as exc:
            logger.error("RequestScheduler: failed to save state — %s", exc)

    # ------------------------------------------------------------------
    # Public API

    def consume(self, provider_name: str) -> bool:
        """Consume one token for the given provider.  Returns True if allowed."""
        bucket = self._buckets.get(provider_name)
        if bucket is None:
            return True  # unknown provider → always allow
        allowed = bucket.consume()
        self.save()
        return allowed

    def remaining(self, provider_name: str) -> int:
        bucket = self._buckets.get(provider_name)
        return bucket.remaining() if bucket else 0

    def summary(self) -> Dict[str, dict]:
        return {
            name: {
                "remaining": b.remaining(),
                "capacity":  b.capacity,
                "period":    b.period,
            }
            for name, b in self._buckets.items()
        }
