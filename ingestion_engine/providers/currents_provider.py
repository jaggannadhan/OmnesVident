"""
CurrentsProvider — Currents API integration for global news coverage.

Free tier: ~600 requests/month  →  budget-gated via RequestScheduler.
Docs: https://currentsapi.services/en/docs/

Auth: apiKey query parameter
Env:  CURRENTS_NEW_API
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

_CURRENTS_BASE = "https://api.currentsapi.services/v1/latest-news"

# Currents API category names
_CATEGORY_MAP = {
    "general":       "news",
    "technology":    "technology",
    "business":      "business",
    "science":       "science",
    "health":        "health",
    "entertainment": "entertainment",
    "sports":        "sports",
    "politics":      "politics",
}


class CurrentsProvider(BaseProvider):
    """
    Provider backed by Currents API.

    Supports country-level filtering and category topics.  Covers all
    tracked regions — used as the primary tier for US/CA/MX and as a
    global supplement when other specialists are not available.

    Args:
        country:     ISO alpha-2 country code (e.g. "US"). Optional.
        category:    News category slug (see _CATEGORY_MAP). Default "news".
        page_size:   Results per request (max 200 free tier). Default 50.
        language:    Language filter. Default "en".
        api_key:     Falls back to CURRENTS_NEW_API env var.
        scheduler:   Optional RequestScheduler for budget enforcement.
        region_code: ISO region code to tag all returned events.
                     Defaults to country.upper() if not specified.
    """

    def __init__(
        self,
        country: Optional[str] = None,
        category: str = "news",
        page_size: int = 50,
        language: str = "en",
        api_key: Optional[str] = None,
        scheduler: Optional["RequestScheduler"] = None,
        region_code: Optional[str] = None,
    ) -> None:
        self._country = country.upper() if country else None
        self._category = _CATEGORY_MAP.get(category.lower(), "news")
        self._page_size = min(page_size, 200)
        self._language = language
        self._api_key = api_key or os.getenv("CURRENTS_NEW_API", "MOCK_API_KEY")
        self._scheduler = scheduler
        self._region_code = region_code or (country.upper() if country else "WORLD")

    @property
    def name(self) -> str:
        label = self._country or "GLOBAL"
        return f"Currents [{label}]"

    async def fetch(self) -> List[NewsEvent]:
        if self._api_key == "MOCK_API_KEY":
            logger.warning("%s: No API key — returning mock data.", self.name)
            return self._mock_events()

        if self._scheduler and not self._scheduler.consume("currents"):
            logger.warning(
                "%s: Monthly quota exhausted — returning mock data as fallback.", self.name
            )
            return self._mock_events()

        params: dict = {
            "apiKey":    self._api_key,
            "language":  self._language,
            "page_size": self._page_size,
        }
        if self._country:
            params["country"] = self._country
        if self._category and self._category != "news":
            params["category"] = self._category

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(_CURRENTS_BASE, params=params)
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
        events: List[NewsEvent] = []
        for article in data.get("news", []):
            try:
                events.append(
                    NewsEvent(
                        title=strip_html(article.get("title", "")),
                        snippet=clean_and_truncate(article.get("description") or ""),
                        source_url=article.get("url", ""),
                        source_name=article.get("author", self.name),
                        region_code=self._region_code,
                        timestamp=self._parse_dt(article.get("published")),
                    )
                )
            except Exception as exc:
                logger.warning("%s: Skipping malformed article — %s", self.name, exc)
        return events

    @staticmethod
    def _parse_dt(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        # Currents returns "2024-01-01 00:00:00 +0000"
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Mock data — representative stories per country

    _MOCK_POOL: Dict[str, tuple] = {
        "US": (
            "US manufacturing output hits three-year high on reshoring demand",
            "ISM data show factory activity expanded for the fifth consecutive month, "
            "led by semiconductor equipment and EV battery component orders.",
            "apnews.com",
        ),
        "CA": (
            "Canada announces C$2.5B fund for critical mineral processing plants",
            "Natural Resources Minister confirmed four provincial partnerships to develop "
            "lithium, cobalt, and nickel refining capacity by 2028.",
            "cbc.ca",
        ),
        "MX": (
            "Mexico nearshoring boom drives record FDI inflows in manufacturing sector",
            "INEGI data show foreign direct investment rose 28% YoY to $36B, with "
            "automotive and electronics clusters in Monterrey and Guadalajara leading.",
            "elfinanciero.com.mx",
        ),
        "GB": (
            "UK government launches digital infrastructure bond for rural broadband",
            "The £1.2B programme will fund fibre-to-the-premises rollout in 400 rural "
            "communities currently underserved by commercial operators.",
            "bbc.co.uk",
        ),
        "AU": (
            "Australia unveils new offshore wind licensing framework for 2026",
            "The Offshore Electricity Infrastructure Act amendments establish five "
            "designated zones along the southern coastline covering 12 GW potential.",
            "abc.net.au",
        ),
    }

    _FALLBACK_MOCK: tuple = (
        "Global economic activity index holds steady in Q1 2026",
        "JP Morgan composite PMI data show world manufacturing and services activity "
        "balanced at 50.4 in February, suggesting resilient but subdued expansion.",
        "reuters.com",
    )

    def _mock_events(self) -> List[NewsEvent]:
        title, snippet, source = self._MOCK_POOL.get(
            self._region_code, self._FALLBACK_MOCK
        )
        return [
            NewsEvent(
                title=title,
                snippet=snippet,
                source_url=f"https://{source}/mock/{self._region_code.lower()}-currents",
                source_name=source,
                region_code=self._region_code,
                timestamp=datetime.now(tz=timezone.utc),
            )
        ]
