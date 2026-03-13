import asyncio
import logging
from typing import List

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class IngestionManager:
    """
    Orchestrates concurrent fetching across all registered providers.

    Providers are run with asyncio.gather so all fetches happen in parallel.
    Individual provider failures are isolated — one broken provider will not
    prevent others from returning results.
    """

    def __init__(self, providers: List[BaseProvider]) -> None:
        self._providers = providers

    def register(self, provider: BaseProvider) -> None:
        self._providers.append(provider)

    async def run(self) -> List[NewsEvent]:
        """Fetch from all providers concurrently and return a flat list of events."""
        if not self._providers:
            logger.warning("IngestionManager: No providers registered.")
            return []

        logger.info(
            "IngestionManager: Starting fetch across %d provider(s).", len(self._providers)
        )

        tasks = [self._safe_fetch(p) for p in self._providers]
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
