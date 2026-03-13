"""
Multi-stage de-duplication for NewsEvent objects.

Stage 1 — Exact URL match (O(1) set lookup after normalization).
Stage 2 — Fuzzy title match within a 24-hour sliding window using
           Levenshtein ratio via `thefuzz`.  Two events are considered
           duplicates when:
             • fuzz.token_sort_ratio(title_a, title_b) >= FUZZY_THRESHOLD
             • AND they share the same region_code

The deduplicator is intentionally stateless: it takes a snapshot list of
NewsEvents and returns cluster groups.  Persistence of "already seen" IDs
across ingestion cycles belongs to a future caching layer (Module 3+).
"""

import hashlib
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from urllib.parse import urlparse, urlunparse

from thefuzz import fuzz

from ingestion_engine.core.models import NewsEvent

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 85        # Minimum Levenshtein similarity (0–100)
SLIDING_WINDOW_HOURS = 24   # Only compare events within this window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """Strip scheme, www prefix, query strings, and fragments for comparison."""
    try:
        parsed = urlparse(url.strip().lower())
        host = parsed.netloc.removeprefix("www.")
        path = parsed.path.rstrip("/")
        return urlunparse(("", host, path, "", "", ""))
    except Exception:
        return url.lower().strip()


def _normalize_title(title: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_title = nfkd.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_title.lower().split())


def _group_id(title: str, region_code: str) -> str:
    """Stable 8-char hex hash used as a cluster identity key."""
    payload = f"{_normalize_title(title)}|{region_code.upper()}"
    return hashlib.sha1(payload.encode()).hexdigest()[:8]


def _within_window(a: datetime, b: datetime) -> bool:
    """Return True if both timestamps are within SLIDING_WINDOW_HOURS of each other."""
    # Ensure both are timezone-aware
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return abs((a - b).total_seconds()) <= SLIDING_WINDOW_HOURS * 3600


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

class DeduplicationResult:
    """
    Holds a cluster of NewsEvents that represent the same story.

    `lead` is the event with the earliest timestamp (i.e. the "breaking" report).
    `duplicates` contains all subsequently-identified copies.
    """

    __slots__ = ("lead", "duplicates", "group_id")

    def __init__(self, lead: NewsEvent) -> None:
        self.lead: NewsEvent = lead
        self.duplicates: List[NewsEvent] = []
        self.group_id: str = _group_id(lead.title, lead.region_code)

    @property
    def secondary_sources(self) -> List[str]:
        return [e.source_url for e in self.duplicates]


def deduplicate(events: List[NewsEvent]) -> List[DeduplicationResult]:
    """
    Accept a flat list of NewsEvents; return deduplicated cluster results.

    Algorithm (O(n²) worst case — acceptable for typical batch sizes ≤ 500):
    1. Index all normalized URLs for instant exact-match lookup.
    2. Iterate events chronologically; for each unassigned event, open a
       new cluster.  Then scan remaining unassigned events:
         a. Skip if URL already seen.
         b. Skip if outside the 24-hour sliding window.
         c. Compute fuzzy title similarity; assign to cluster if >= threshold
            AND region matches.
    """

    if not events:
        return []

    # Sort chronologically so the earliest article becomes the lead
    sorted_events = sorted(
        events,
        key=lambda e: e.timestamp if e.timestamp.tzinfo else e.timestamp.replace(tzinfo=timezone.utc),
    )

    seen_urls: Dict[str, int] = {}   # normalized_url -> cluster index
    clusters: List[DeduplicationResult] = []
    assigned: List[bool] = [False] * len(sorted_events)

    for i, event_i in enumerate(sorted_events):
        if assigned[i]:
            continue

        norm_url_i = _normalize_url(event_i.source_url)

        # Stage 1: exact URL already belongs to a cluster → skip
        if norm_url_i in seen_urls:
            assigned[i] = True
            clusters[seen_urls[norm_url_i]].duplicates.append(event_i)
            continue

        # Open a new cluster
        cluster = DeduplicationResult(lead=event_i)
        cluster_idx = len(clusters)
        clusters.append(cluster)
        assigned[i] = True
        seen_urls[norm_url_i] = cluster_idx

        norm_title_i = _normalize_title(event_i.title)

        for j in range(i + 1, len(sorted_events)):
            if assigned[j]:
                continue

            event_j = sorted_events[j]

            # Stage 1: exact URL duplicate
            norm_url_j = _normalize_url(event_j.source_url)
            if norm_url_j == norm_url_i or norm_url_j in seen_urls:
                assigned[j] = True
                clusters[seen_urls.get(norm_url_j, cluster_idx)].duplicates.append(event_j)
                seen_urls[norm_url_j] = cluster_idx
                continue

            # Sliding window gate
            if not _within_window(event_i.timestamp, event_j.timestamp):
                continue

            # Stage 2: fuzzy title match (same region only)
            if event_j.region_code.upper() != event_i.region_code.upper():
                continue

            similarity = fuzz.token_sort_ratio(
                norm_title_i, _normalize_title(event_j.title)
            )
            if similarity >= FUZZY_THRESHOLD:
                assigned[j] = True
                cluster.duplicates.append(event_j)
                seen_urls[norm_url_j] = cluster_idx
                logger.debug(
                    "Duplicate found (sim=%d): '%s' ~ '%s'",
                    similarity,
                    event_i.title[:60],
                    event_j.title[:60],
                )

    logger.info(
        "Deduplication: %d events → %d clusters (removed %d duplicates).",
        len(events),
        len(clusters),
        len(events) - len(clusters),
    )
    return clusters
