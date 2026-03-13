import os
import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.core.normalizer import clean_and_truncate, strip_html
from ingestion_engine.providers.base import BaseProvider

logger = logging.getLogger(__name__)

NEWSDATA_BASE_URL = "https://newsdata.io/api/1/news"


class NewsDataProvider(BaseProvider):
    """
    Provider for newsdata.io REST API.

    Docs: https://newsdata.io/documentation
    Set NEWSDATA_API_KEY environment variable or pass api_key directly.
    """

    def __init__(
        self,
        country: str,
        api_key: Optional[str] = None,
        language: str = "en",
        page_size: int = 10,
    ) -> None:
        self._country = country.lower()
        self._api_key = api_key or os.getenv("NEWSDATA_API_KEY", "MOCK_API_KEY")
        self._language = language
        self._page_size = page_size

    @property
    def name(self) -> str:
        return f"NewsData.io [{self._country.upper()}]"

    async def fetch(self) -> List[NewsEvent]:
        params = {
            "apikey": self._api_key,
            "country": self._country,
            "language": self._language,
            "size": self._page_size,
        }

        if self._api_key == "MOCK_API_KEY":
            logger.warning("%s: No API key — returning mock data.", self.name)
            return self._mock_events()

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(NEWSDATA_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                logger.error("%s: HTTP %s — %s", self.name, exc.response.status_code, exc)
                return []
            except httpx.RequestError as exc:
                logger.error("%s: Request failed — %s", self.name, exc)
                return []

        return self._parse(data)

    def _parse(self, data: dict) -> List[NewsEvent]:
        events: List[NewsEvent] = []
        for article in data.get("results", []):
            try:
                raw_description = article.get("description") or article.get("content") or ""
                events.append(
                    NewsEvent(
                        title=strip_html(article.get("title", "")),
                        snippet=clean_and_truncate(raw_description),
                        source_url=article.get("link", ""),
                        source_name=article.get("source_id", self.name),
                        region_code=self._country.upper(),
                        timestamp=self._parse_dt(article.get("pubDate")),
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

    # One representative headline per category, rotated per country so every
    # region produces varied, classifiable stories in mock mode.
    _MOCK_POOL = [
        ("Parliament votes on sweeping election reform bill",
         "Legislators debated the proposed changes to voting procedures late into the night."),
        ("Central bank raises interest rates amid rising inflation",
         "The decision sent stock markets lower as investors weighed the economic outlook."),
        ("Scientists discover new exoplanet with signs of water vapour",
         "Researchers published peer-reviewed findings using data from the space telescope."),
        ("Health ministry approves fast-tracked vaccine for new outbreak",
         "The FDA-equivalent agency cleared the drug after accelerated clinical trials."),
        ("Tech giant unveils AI-powered smartphone with on-device machine learning",
         "The new chip enables real-time language translation without a cloud connection."),
        ("National football team reaches World Cup semi-finals",
         "The squad defeated their opponents in a penalty shootout before a record crowd."),
        ("Award-winning director announces sequel to record-breaking film",
         "The studio confirmed the Netflix release date alongside the new cast lineup."),
        ("Military ceasefire brokered after UN Security Council emergency session",
         "NATO members called for immediate humanitarian aid access to the conflict zone."),
    ]

    def _mock_events(self) -> List[NewsEvent]:
        code = self._country.upper()
        # Rotate through the pool so each country gets a different pair of stories
        offset = sum(ord(c) for c in code) % len(self._MOCK_POOL)
        events = []
        for i in range(2):
            title, snippet = self._MOCK_POOL[(offset + i) % len(self._MOCK_POOL)]
            events.append(
                NewsEvent(
                    title=f"[{code}] {title}",
                    snippet=snippet,
                    source_url=f"https://example.com/mock/{code.lower()}-{i + 1}",
                    source_name="MockSource",
                    region_code=code,
                    timestamp=datetime.now(tz=timezone.utc),
                )
            )
        return events
