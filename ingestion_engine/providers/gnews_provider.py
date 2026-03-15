"""
GNewsProvider — GNews API integration for US/Canada coverage.

Free tier: 100 requests/day  →  budget-gated via RequestScheduler.
Docs: https://gnews.io/docs/v4

Env: GNEWS_API
"""

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

import httpx

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.core.normalizer import clean_and_truncate, strip_html
from ingestion_engine.providers.base import BaseProvider

if TYPE_CHECKING:
    from ingestion_engine.core.scheduler import RequestScheduler

logger = logging.getLogger(__name__)

_GNEWS_BASE = "https://gnews.io/api/v4/top-headlines"

# GNews country codes that map cleanly to ISO alpha-2
_SUPPORTED_COUNTRIES = {"us", "ca", "mx", "gb", "au", "in"}


class GNewsProvider(BaseProvider):
    """
    Provider backed by GNews API v4.

    Args:
        country:    ISO alpha-2 country code (e.g. "us").
        category:   GNews topic: general|world|nation|business|technology|
                    entertainment|sports|science|health.  Default "general".
        max:        Results per request (1-10 free tier). Default 10.
        api_key:    Falls back to GNEWS_API env var.
        scheduler:  Optional RequestScheduler for budget enforcement.
    """

    def __init__(
        self,
        country: str = "us",
        category: str = "general",
        max_results: int = 10,
        api_key: Optional[str] = None,
        scheduler: Optional["RequestScheduler"] = None,
    ) -> None:
        self._country = country.lower()
        self._category = category
        self._max = min(max_results, 10)
        self._api_key = api_key or os.getenv("GNEWS_API", "MOCK_API_KEY")
        self._scheduler = scheduler

    @property
    def name(self) -> str:
        return f"GNews [{self._country.upper()}]"

    async def fetch(self) -> List[NewsEvent]:
        if self._api_key == "MOCK_API_KEY":
            logger.warning("%s: No API key — returning mock data.", self.name)
            return self._mock_events()

        if self._scheduler and not self._scheduler.consume("gnews"):
            logger.warning(
                "%s: Daily quota exhausted — returning mock data as fallback.", self.name
            )
            return self._mock_events()

        params = {
            "country":  self._country,
            "category": self._category,
            "max":      self._max,
            "lang":     "en",
            "apikey":   self._api_key,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(_GNEWS_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error("%s: HTTP %s — %s", self.name, exc.response.status_code, exc)
                return []
            except httpx.RequestError as exc:
                logger.error("%s: Request failed — %s", self.name, exc)
                return []

        return self._parse(data)

    def _parse(self, data: dict) -> List[NewsEvent]:
        region = self._country.upper()
        events: List[NewsEvent] = []
        for article in data.get("articles", []):
            try:
                events.append(
                    NewsEvent(
                        title=strip_html(article.get("title", "")),
                        snippet=clean_and_truncate(article.get("description") or ""),
                        source_url=article.get("url", ""),
                        source_name=(article.get("source") or {}).get("name", self.name),
                        region_code=region,
                        timestamp=self._parse_dt(article.get("publishedAt")),
                    )
                )
            except Exception as exc:
                logger.warning("%s: Skipping malformed article — %s", self.name, exc)
        return events

    @staticmethod
    def _parse_dt(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Mock data — representative US stories

    _MOCK_POOL: Dict[str, List[tuple]] = {
        "us": [
            (
                "Senate passes bipartisan infrastructure maintenance bill",
                "The $180B measure earmarks funds for bridge repairs, rail upgrades, and "
                "broadband expansion in rural counties across 32 states.",
                "apnews.com",
                "US",
            ),
            (
                "Federal Reserve holds rates steady amid cooling inflation data",
                "The FOMC voted 11-1 to keep the benchmark rate at 5.25%, citing "
                "moderated CPI readings and stable labor market conditions.",
                "reuters.com",
                "US",
            ),
        ],
        "ca": [
            (
                "Bank of Canada signals pause in rate hike cycle",
                "Governor Tiff Macklem cited easing core inflation and slowing housing "
                "activity as reasons for holding the overnight rate at 5.0%.",
                "theglobeandmail.com",
                "CA",
            ),
        ],
    }

    def _mock_events(self) -> List[NewsEvent]:
        pool = self._MOCK_POOL.get(self._country, self._MOCK_POOL["us"])
        events = []
        for title, snippet, source, region in pool:
            events.append(
                NewsEvent(
                    title=title,
                    snippet=snippet,
                    source_url=f"https://{source}/mock/{self._country}-gnews",
                    source_name=source,
                    region_code=region,
                    timestamp=datetime.now(tz=timezone.utc),
                )
            )
        return events
