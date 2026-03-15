"""
bundler.py — RegionBundler: groups city names into OR-query bundles.

Each bundle covers one ISO 3166-2 subdivision and contains at most
MAX_CITIES_PER_BUNDLE city names joined as "(City1 OR City2 OR City3)".

Bundles are fed to NewsCatcherProvider or NewsDataProvider keyword queries
to maximise sub-national news density per API credit.

Why bundling beats individual city queries:
  • 1 API call covers 5 cities instead of 5 calls for 1 city each.
  • Reduces daily/monthly quota consumption by ~5×.
  • Slightly broader context catches cross-city stories (e.g. "Tamil Nadu
    transport ministry" without a specific city name).

Tag-heavy post-processing (TagEnhancer as Source of Truth):
  After a bundled fetch returns a mixed bag the existing IntelligencePipeline
  runs TagEnhancer.enhance() on every event BEFORE deduplication.  TagEnhancer
  scans title + snippet for the specific city names in CITY_TO_STATE and
  re-assigns region_code accordingly.  A query "(Austin OR Dallas)" therefore
  produces two distinct subdivision blips on the globe — TagEnhancer splits
  the result automatically with no bundler-level logic required.

Usage:
    from ingestion_engine.core.bundler import RegionBundler

    bundler = RegionBundler()

    # First bundle (≤5 cities) for every always-on subdivision:
    for bundle in bundler.first_bundles(["IN-TN", "US-TX"]):
        providers.append(
            NewsCatcherProvider(
                country=bundle.country.lower(),
                subdivision=bundle.subdivision,
                query_keywords=bundle.cities,
            )
        )

    # All bundles for a single subdivision:
    for bundle in bundler.get_bundles("US-TX"):
        print(bundle.query)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from intelligence_layer.geo_tagger import CITY_TO_STATE

MAX_CITIES_PER_BUNDLE = 5


@dataclass
class RegionBundle:
    """
    One query bundle targeting a single ISO 3166-2 subdivision.

    Attributes:
        subdivision: ISO 3166-2 code, e.g. "US-TX".
        country:     ISO alpha-2 country code derived from subdivision, e.g. "US".
        cities:      Up to MAX_CITIES_PER_BUNDLE original-case city names.
        query:       Ready-to-use OR query string: "(Houston OR Dallas OR Austin)".
    """

    subdivision: str
    country: str
    cities: List[str]
    query: str

    @classmethod
    def from_cities(cls, subdivision: str, cities: List[str]) -> "RegionBundle":
        country = subdivision.split("-")[0]
        query = "(" + " OR ".join(cities) + ")"
        return cls(subdivision=subdivision, country=country, cities=list(cities), query=query)


class RegionBundler:
    """
    Builds RegionBundle objects by grouping CITY_TO_STATE entries into
    chunks of at most MAX_CITIES_PER_BUNDLE cities per subdivision.

    The bundler is constructed once and is read-only thereafter.
    """

    def __init__(self) -> None:
        # Group original-case city names by their subdivision code.
        by_sub: Dict[str, List[str]] = {}
        for city, sub in CITY_TO_STATE.items():
            by_sub.setdefault(sub, []).append(city)

        # Chunk each subdivision's city list into bundles of MAX_CITIES_PER_BUNDLE.
        self._bundles: Dict[str, List[RegionBundle]] = {}
        for sub, cities in by_sub.items():
            chunks = [
                cities[i: i + MAX_CITIES_PER_BUNDLE]
                for i in range(0, len(cities), MAX_CITIES_PER_BUNDLE)
            ]
            self._bundles[sub] = [RegionBundle.from_cities(sub, chunk) for chunk in chunks]

    # ------------------------------------------------------------------
    # Public API

    def get_bundles(self, subdivision: str) -> List[RegionBundle]:
        """All bundles for a single subdivision (e.g. 'US-TX')."""
        return self._bundles.get(subdivision.upper(), [])

    def first_bundle(self, subdivision: str) -> Optional[RegionBundle]:
        """The first (highest-priority) bundle for a subdivision, or None."""
        bundles = self.get_bundles(subdivision)
        return bundles[0] if bundles else None

    def first_bundles(self, subdivisions: List[str]) -> List[RegionBundle]:
        """
        Return the first bundle for each subdivision in the given list,
        skipping any with no coverage in CITY_TO_STATE.
        """
        result: List[RegionBundle] = []
        for sub in subdivisions:
            b = self.first_bundle(sub)
            if b:
                result.append(b)
        return result

    def all_bundles(self, country: Optional[str] = None) -> List[RegionBundle]:
        """
        Every bundle across all subdivisions, optionally filtered by
        country code (e.g. 'US' returns only US-* bundles).
        """
        result: List[RegionBundle] = []
        for bundles in self._bundles.values():
            for b in bundles:
                if country is None or b.country == country.upper():
                    result.append(b)
        return result

    def subdivisions(self) -> List[str]:
        """All subdivision codes that have at least one bundle."""
        return list(self._bundles.keys())

    def bundle_count(self, subdivision: str) -> int:
        """Number of bundles for the given subdivision."""
        return len(self._bundles.get(subdivision.upper(), []))

    def summary(self) -> Dict[str, int]:
        """
        Returns {subdivision: bundle_count} for every tracked subdivision.
        Useful for logging at startup.
        """
        return {sub: len(bundles) for sub, bundles in self._bundles.items()}
