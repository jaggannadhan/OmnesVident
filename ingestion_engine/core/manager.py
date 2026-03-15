import asyncio
import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.providers.base import BaseProvider

if TYPE_CHECKING:
    from ingestion_engine.core.scheduler import RequestScheduler

logger = logging.getLogger(__name__)


class IngestionManager:
    """
    Orchestrates concurrent fetching across all registered providers.

    Regular providers run on every cycle.  Sub-national providers are run in
    rotating batches (controlled by `batch_size` and `cycle`) so that a large
    list of state/province providers does not exhaust API rate limits on every
    ingestion run.
    """

    def __init__(self, providers: List[BaseProvider]) -> None:
        self._providers = providers

    def register(self, provider: BaseProvider) -> None:
        self._providers.append(provider)

    async def run(
        self,
        sub_national: Optional[List[BaseProvider]] = None,
        always_on: Optional[List[BaseProvider]] = None,
        batch_size: int = 6,
        cycle: int = 0,
    ) -> List[NewsEvent]:
        """
        Fetch from all providers concurrently and return a flat list of events.

        Args:
            always_on:    Sub-national providers that run on EVERY cycle
                          (highest-priority regions, e.g. IN-TN, IN-MH, US-CA).
            sub_national: Rotating pool of state/province-level providers.
                          Only a batch of `batch_size` are queried per run.
            batch_size:   Number of rotating sub-national providers per cycle.
            cycle:        Determines which batch slice is selected.
        """
        active = list(self._providers)

        if always_on:
            active.extend(always_on)
            logger.info(
                "IngestionManager: %d always-on sub-national provider(s) added.", len(always_on)
            )

        if sub_national:
            n = len(sub_national)
            if n > 0:
                start = (cycle * batch_size) % n
                batch = [sub_national[(start + i) % n] for i in range(min(batch_size, n))]
                active.extend(batch)
                logger.info(
                    "IngestionManager: Sub-national batch — %d provider(s) starting at index %d "
                    "(cycle %d, pool size %d).",
                    len(batch), start, cycle, n,
                )

        if not active:
            logger.warning("IngestionManager: No providers registered.")
            return []

        logger.info(
            "IngestionManager: Starting fetch across %d provider(s).", len(active)
        )

        tasks = [self._safe_fetch(p) for p in active]
        results = await asyncio.gather(*tasks)

        all_events: List[NewsEvent] = []
        for events in results:
            all_events.extend(events)

        logger.info("IngestionManager: Collected %d total events.", len(all_events))
        return all_events

    @staticmethod
    async def _safe_fetch(provider: BaseProvider) -> List[NewsEvent]:
        try:
            events = await provider.fetch()
            logger.info("%s: Fetched %d events.", provider.name, len(events))
            return events
        except Exception as exc:
            logger.error("%s: Unhandled exception during fetch — %s", provider.name, exc)
            return []


# ---------------------------------------------------------------------------
# ProviderRouter — per-spec Module 10.0
# ---------------------------------------------------------------------------

class ProviderRouter:
    """
    Lightweight router that maps country codes to their assigned provider tier
    and enforces failover when a tier's budget is exhausted.

    The full routing logic and provider instantiation live in
    `ingestion_engine/factory.py`.  This class is the manager-level interface
    for querying the current routing decision without constructing providers.

    Tier assignments:
        gnews      — US, CA, MX
        worldnews  — IN
        mediastack — GB, DE, FR, IT, UA, ES, NL, PL, SE
        newsdata   — global fallback + all other countries
    """

    _ROUTING_TABLE: Dict[str, str] = {
        "US": "currents",  "CA": "currents",  "MX": "currents",
        "IN": "worldnews",
        "GB": "mediastack","DE": "mediastack","FR": "mediastack",
        "IT": "mediastack","UA": "mediastack","ES": "mediastack",
        "NL": "mediastack","PL": "mediastack","SE": "mediastack",
    }

    _FAILOVER: Dict[str, str] = {
        "currents":   "newsdata",
        "worldnews":  "newsdata",
        "mediastack": "newsdata",
    }

    def __init__(self, scheduler: Optional["RequestScheduler"] = None) -> None:
        self._scheduler = scheduler

    def resolve(self, country_code: str) -> str:
        """
        Return the effective provider tier for *country_code*.

        Checks the scheduler's remaining budget; if zero, returns the
        failover tier so the caller can substitute a backup provider.
        """
        tier = self._ROUTING_TABLE.get(country_code.upper(), "newsdata")

        if self._scheduler and tier != "newsdata":
            if self._scheduler.remaining(tier) == 0:
                failover = self._FAILOVER.get(tier, "newsdata")
                logger.warning(
                    "ProviderRouter: %s quota exhausted for %s → failover to %s.",
                    tier, country_code.upper(), failover,
                )
                return failover

        return tier

    def budget_summary(self) -> Dict[str, dict]:
        if self._scheduler:
            return self._scheduler.summary()
        return {}
