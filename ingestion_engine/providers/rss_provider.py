import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

import feedparser

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.core.normalizer import clean_and_truncate, strip_html
from ingestion_engine.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class RSSProvider(BaseProvider):
    """
    Provider that aggregates one or more RSS/Atom feeds.

    feedparser is synchronous; each feed is run in a thread-pool executor
    to avoid blocking the event loop.
    """

    def __init__(self, feed_urls: List[str], region_code: str) -> None:
        if not feed_urls:
            raise ValueError("At least one feed URL is required.")
        self._feed_urls = feed_urls
        self._region_code = region_code.upper()

    @property
    def name(self) -> str:
        return f"RSS [{self._region_code}]"

    async def fetch(self) -> List[NewsEvent]:
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(None, self._parse_feed, url)
            for url in self._feed_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        events: List[NewsEvent] = []
        for url, result in zip(self._feed_urls, results):
            if isinstance(result, Exception):
                logger.error("%s: Failed to parse %s — %s", self.name, url, result)
            else:
                events.extend(result)
        return events

    def _parse_feed(self, url: str) -> List[NewsEvent]:
        parsed = feedparser.parse(url)
        if parsed.get("bozo") and not parsed.get("entries"):
            raise ValueError(f"Malformed feed at {url}: {parsed.get('bozo_exception')}")

        source_name = parsed.feed.get("title", url)
        events: List[NewsEvent] = []

        for entry in parsed.entries:
            try:
                raw_summary = entry.get("summary") or entry.get("description") or ""
                events.append(
                    NewsEvent(
                        title=strip_html(entry.get("title", "")),
                        snippet=clean_and_truncate(raw_summary),
                        source_url=entry.get("link", ""),
                        source_name=source_name,
                        region_code=self._region_code,
                        timestamp=self._parse_dt(entry),
                    )
                )
            except Exception as exc:
                logger.warning("%s: Skipping entry — %s", self.name, exc)

        return events

    @staticmethod
    def _parse_dt(entry) -> datetime:
        # feedparser normalises to a time.struct_time in 'published_parsed'
        if entry.get("published_parsed"):
            import time
            ts = time.mktime(entry["published_parsed"])
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if entry.get("published"):
            try:
                return parsedate_to_datetime(entry["published"]).astimezone(timezone.utc)
            except Exception:
                pass
        return datetime.now(tz=timezone.utc)
