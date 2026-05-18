"""
Region-code expansion shared by the Firestore and SQLite query paths.

A user picking "IN" in the region filter expects to see Indian national news
AND the state-level feeds (IN-TN, IN-MH, …) we ingest separately. Without
this helper, the equality filter `region_code == "IN"` only matches the
national feed, which silently hides most regional stories.

The expansion is loaded once from `ingestion_engine/regions_to_track.json`
(the same file the public /regions endpoint serves) and cached for the
process lifetime.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_REGIONS_PATH = (
    Path(__file__).resolve().parent.parent
    / "ingestion_engine"
    / "regions_to_track.json"
)


@lru_cache(maxsize=1)
def _sub_regions_by_country() -> Dict[str, List[str]]:
    """Load and cache the country → list-of-sub-region-codes map."""
    try:
        with open(_REGIONS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {
            country.upper(): [r["code"].upper() for r in regions]
            for country, regions in data.items()
        }
    except Exception as exc:
        logger.warning("regions: could not load %s — %s", _REGIONS_PATH, exc)
        return {}


def expand_region_code(code: str) -> List[str]:
    """
    Return all region codes that should match a user-supplied region filter.

    For a country-level code ("IN"), this is the country plus every
    sub-region we ingest for it (["IN", "IN-TN", "IN-MH", …]). For a
    sub-region code that's already specific ("IN-TN") this is just that
    single code — sub-regions are leaves, no further nesting.

    The returned list is always non-empty and starts with the user-supplied
    code (uppercased), so callers can treat `result[0]` as "the canonical
    country code" when needed.
    """
    code_upper = code.upper()
    if "-" in code_upper:
        return [code_upper]
    sub_regions = _sub_regions_by_country().get(code_upper, [])
    return [code_upper, *sub_regions]
