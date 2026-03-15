"""
factory.py — ProviderFactory & ProviderRouter

ProviderRouter maps each country_code to its designated specialist API:

  US / CA / MX  →  Currents API       (600 req/month;  CURRENTS_NEW_API)
  IN            →  World News API     (1,500 req/month; WORLD_NEWS_API_KEY)
  GB/DE/FR/IT/  →  Mediastack         (500 req/month;  MEDIA_STACK_NEWS_API_KEY)
  UA/EU
  US / CA       →  GNews API          (100 req/day;  GNEWS_API) — supplements Currents
  GLOBAL        →  NewsData.io        (always-on baseline fallback)

ProviderFactory instantiates the correct provider class, wiring in the
RequestScheduler for budget enforcement and auto-failover.

Usage (in main.py):
    scheduler = RequestScheduler()
    factory   = ProviderFactory(scheduler)
    providers = factory.build_all()
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from ingestion_engine.core.scheduler import RequestScheduler
from ingestion_engine.providers.base import BaseProvider
from ingestion_engine.providers.currents_provider import CurrentsProvider
from ingestion_engine.providers.gnews_provider import GNewsProvider
from ingestion_engine.providers.mediastack_provider import MediastackProvider
from ingestion_engine.providers.newsdata_io import NewsDataProvider
from ingestion_engine.providers.newscatcher_provider import NewsCatcherProvider
from ingestion_engine.providers.worldnews_provider import WorldNewsProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing table  (country_code upper → provider tier name)
# ---------------------------------------------------------------------------

ROUTING_TABLE: Dict[str, str] = {
    # Currents API tier — North America
    "US": "currents",
    "CA": "currents",
    "MX": "currents",
    # World News tier — India
    "IN": "worldnews",
    # Mediastack tier — Europe
    "GB": "mediastack",
    "DE": "mediastack",
    "FR": "mediastack",
    "IT": "mediastack",
    "UA": "mediastack",
    "ES": "mediastack",
    "NL": "mediastack",
    "PL": "mediastack",
    "SE": "mediastack",
}

# EU bundle — sent as a single Mediastack request for efficiency
_EU_BUNDLE = ["gb", "de", "fr", "it", "ua"]

# India always-on subdivisions for World News API city queries
_INDIA_ALWAYS_ON: Dict[str, str] = {
    "IN-TN": "Chennai Tamil Nadu",
    "IN-MH": "Mumbai Maharashtra",
    "IN-DL": "Delhi New Delhi",
    "IN-KA": "Bengaluru Karnataka",
    "IN-WB": "Kolkata West Bengal",
    "IN-GJ": "Ahmedabad Gujarat",
    "IN-AP": "Visakhapatnam Andhra Pradesh",
}


class ProviderRouter:
    """
    Maps a country_code to a provider tier name, with failover awareness.

    Failover chain:
        currents   → newsdata (on exhaustion)
        worldnews  → newsdata + newscatcher (on exhaustion)
        mediastack → newsdata (on exhaustion)
    """

    FAILOVER: Dict[str, str] = {
        "currents":   "newsdata",
        "worldnews":  "newsdata",
        "mediastack": "newsdata",
    }

    def __init__(self, scheduler: RequestScheduler) -> None:
        self._scheduler = scheduler

    def resolve(self, country_code: str) -> str:
        """Return the effective provider tier, failing over if quota is zero."""
        tier = ROUTING_TABLE.get(country_code.upper(), "newsdata")

        if tier != "newsdata" and self._scheduler.remaining(tier) == 0:
            failover = self.FAILOVER.get(tier, "newsdata")
            logger.warning(
                "ProviderRouter: %s quota for %s exhausted → failing over to %s.",
                tier, country_code.upper(), failover,
            )
            return failover

        return tier

    def budget_summary(self) -> Dict[str, dict]:
        return self._scheduler.summary()


class ProviderFactory:
    """
    Instantiates the full specialist provider set for one ingestion cycle.

    Supplements (not replaces) the existing NewsData.io country providers
    defined in main.py.  Callers should merge both lists.
    """

    def __init__(self, scheduler: Optional[RequestScheduler] = None) -> None:
        self._scheduler = scheduler or RequestScheduler()
        self._router = ProviderRouter(self._scheduler)

    # ------------------------------------------------------------------

    def build_us_providers(self) -> List[BaseProvider]:
        """Currents + GNews providers for North America (run in parallel)."""
        providers: List[BaseProvider] = []
        tier = self._router.resolve("US")
        if tier == "currents":
            api_key = os.getenv("CURRENTS_NEW_API")
            providers.extend(
                CurrentsProvider(country=c, api_key=api_key, scheduler=self._scheduler)
                for c in ["US", "CA", "MX"]
            )
        else:
            providers.extend(NewsDataProvider(country=c) for c in ["us", "ca", "mx"])

        # GNews supplements Currents with a different article pool (100 req/day)
        gnews_key = os.getenv("GNEWS_API")
        if gnews_key:
            providers.extend(
                GNewsProvider(country=c, api_key=gnews_key, scheduler=self._scheduler)
                for c in ["us", "ca"]
            )

        return providers

    def build_india_providers(self) -> List[BaseProvider]:
        """World News API for India — country baseline + subdivision city queries."""
        tier = self._router.resolve("IN")
        providers: List[BaseProvider] = []

        if tier == "worldnews":
            api_key = os.getenv("WORLD_NEWS_API_KEY")
            providers.append(
                WorldNewsProvider(country="in", api_key=api_key, scheduler=self._scheduler)
            )
            for sub, city_query in _INDIA_ALWAYS_ON.items():
                providers.append(
                    WorldNewsProvider(
                        country="in",
                        city_query=city_query,
                        subdivision=sub,
                        api_key=api_key,
                        scheduler=self._scheduler,
                    )
                )
        else:
            # Failover: NewsData + NewsCatcher
            providers.append(NewsDataProvider(country="in"))
            for sub, keywords in {
                "IN-TN": ["Chennai", "Madurai", "Tamil Nadu"],
                "IN-MH": ["Mumbai", "Pune", "Maharashtra"],
                "IN-DL": ["Delhi", "New Delhi"],
                "IN-KA": ["Bengaluru", "Bangalore", "Karnataka"],
                "IN-WB": ["Kolkata", "West Bengal"],
            }.items():
                providers.append(
                    NewsCatcherProvider(country="in", subdivision=sub, query_keywords=keywords)
                )

        return providers

    def build_eu_providers(self) -> List[BaseProvider]:
        """Single Mediastack request covering the EU bundle."""
        tier = self._router.resolve("GB")
        if tier == "mediastack":
            return [
                MediastackProvider(
                    countries=_EU_BUNDLE,
                    api_key=os.getenv("MEDIA_STACK_NEWS_API_KEY"),
                    scheduler=self._scheduler,
                )
            ]
        # Failover
        return [NewsDataProvider(country=c) for c in ["gb", "de", "fr", "it"]]

    def build_all(self) -> List[BaseProvider]:
        providers: List[BaseProvider] = []
        providers.extend(self.build_us_providers())
        providers.extend(self.build_india_providers())
        providers.extend(self.build_eu_providers())

        logger.info(
            "ProviderFactory: built %d specialist provider(s). Budget: %s",
            len(providers),
            {k: f"{v['remaining']}/{v['capacity']} {v['period']}"
             for k, v in self._router.budget_summary().items()},
        )
        return providers

    @property
    def router(self) -> ProviderRouter:
        return self._router

    @property
    def scheduler(self) -> RequestScheduler:
        return self._scheduler
