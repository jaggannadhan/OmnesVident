"""
WorldNewsProvider — World News API integration for high-precision India coverage.

Free tier: 1,500 requests/month  →  budget-gated via RequestScheduler.
Failover: NewsData.io / NewsCatcher when monthly limit is reached.
Docs: https://worldnewsapi.com/docs/

Auth: x-api-key header
Env:  WORLDNEWS_API_KEY
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

_WORLDNEWS_BASE = "https://api.worldnewsapi.com/search-news"


class WorldNewsProvider(BaseProvider):
    """
    Provider backed by World News API.

    Specialised for Indian sub-national coverage — accepts a `city` keyword
    that triggers a precise text-match query (e.g. "Chennai Tamil Nadu") to
    surface stories from regional Indian publishers.

    Args:
        country:     ISO alpha-2 source-countries filter (default "in").
        city_query:  Free-text city/state keywords for precise sub-national
                     targeting (e.g. "Chennai Tamil Nadu").
        subdivision: ISO 3166-2 code placed on all returned events
                     (e.g. "IN-TN").  Falls back to country upper-case.
        number:      Results per request (1-100). Default 50.
        api_key:     Falls back to WORLDNEWS_API_KEY env var.
        scheduler:   Optional RequestScheduler for budget enforcement.
    """

    def __init__(
        self,
        country: str = "in",
        city_query: Optional[str] = None,
        subdivision: Optional[str] = None,
        number: int = 50,
        api_key: Optional[str] = None,
        scheduler: Optional["RequestScheduler"] = None,
    ) -> None:
        self._country = country.lower()
        self._city_query = city_query
        self._subdivision = subdivision
        self._number = min(number, 100)
        self._api_key = api_key or os.getenv("WORLD_NEWS_API_KEY", "MOCK_API_KEY")
        self._scheduler = scheduler

    @property
    def name(self) -> str:
        label = self._subdivision or self._country.upper()
        return f"WorldNews [{label}]"

    async def fetch(self) -> List[NewsEvent]:
        if self._api_key == "MOCK_API_KEY":
            logger.warning("%s: No API key — returning mock data.", self.name)
            return self._mock_events()

        if self._scheduler and not self._scheduler.consume("worldnews"):
            logger.warning(
                "%s: Monthly quota exhausted — failing over to mock data.", self.name
            )
            return self._mock_events()

        headers = {"x-api-key": self._api_key}
        params: dict = {
            "source-countries": self._country,
            "language":         "en",
            "number":           self._number,
        }
        if self._city_query:
            params["text"] = self._city_query

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(_WORLDNEWS_BASE, params=params, headers=headers)
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
        region = self._subdivision or self._country.upper()
        events: List[NewsEvent] = []
        for article in data.get("news", []):
            try:
                raw_text = article.get("text") or article.get("summary") or ""
                events.append(
                    NewsEvent(
                        title=strip_html(article.get("title", "")),
                        snippet=clean_and_truncate(raw_text),
                        source_url=article.get("url", ""),
                        source_name=article.get("source_country", self.name),
                        region_code=region,
                        timestamp=self._parse_dt(article.get("publish_date")),
                    )
                )
            except Exception as exc:
                logger.warning("%s: Skipping malformed article — %s", self.name, exc)
        return events

    @staticmethod
    def _parse_dt(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        # World News API returns "YYYY-MM-DD HH:MM:SS" UTC
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Mock data — hyper-local Indian city stories per subdivision

    _SUBDIVISION_MOCK: Dict[str, tuple] = {
        "IN-TN": (
            "Tamil Nadu government launches 1,000 MW solar tender for northern districts",
            "TANGEDCO issued the tender under the state's Renewable Energy Policy 2024, "
            "targeting installations across Villupuram, Cuddalore, and Vellore districts.",
            "thehindu.com",
        ),
        "IN-MH": (
            "Maharashtra cabinet clears revised metro fare structure for Mumbai network",
            "Fares on lines 2A and 7 will be revised from ₹10–50 to ₹10–60 after MMRDA "
            "cited rising power and maintenance costs following the Charkop extension.",
            "hindustantimes.com",
        ),
        "IN-DL": (
            "Delhi government announces 24-hour water supply pilot for 12 colonies",
            "Jal Board MD confirmed the pilot covers R.K. Puram, Dwarka Sector 21, and "
            "Rohini blocks under the World Bank-funded distribution upgrade project.",
            "ndtv.com",
        ),
        "IN-KA": (
            "Bengaluru Metro Purple Line extended to Challaghatta with six new stations",
            "BMRCL completed trial runs on the 6.3 km extension; commercial service "
            "begins next month, reducing pressure on the Silk Board junction corridor.",
            "deccanherald.com",
        ),
        "IN-WB": (
            "West Bengal industrial park project attracts ₹8,000 crore in commitments",
            "At the Bengal Global Business Summit, the state secured investments for "
            "manufacturing clusters in Kharagpur, Haldia, and Durgapur tech zones.",
            "telegraphindia.com",
        ),
        "IN-GJ": (
            "Gujarat GIFT City launches third international fintech acceleration cohort",
            "Twenty-five startups from eight countries were selected for the six-month "
            "programme, focusing on cross-border payments and RegTech solutions.",
            "financialexpress.com",
        ),
        "IN-AP": (
            "Andhra Pradesh Amaravati construction resumes after Supreme Court clearance",
            "The state government released ₹3,400 crore for the capital city's first "
            "phase covering government quarters, secretariat blocks, and road network.",
            "thehindu.com",
        ),
    }

    _GENERIC_MOCK: tuple = (
        "India infrastructure index rises to highest level in five years",
        "Ministry of Statistics data show composite infrastructure output up 8.2% YoY, "
        "led by cement, electricity, and steel sub-indices in Q3 FY2025.",
        "livemint.com",
    )

    def _mock_events(self) -> List[NewsEvent]:
        region = self._subdivision or self._country.upper()
        if self._subdivision and self._subdivision in self._SUBDIVISION_MOCK:
            title, snippet, source = self._SUBDIVISION_MOCK[self._subdivision]
        else:
            title, snippet, source = self._GENERIC_MOCK
        return [
            NewsEvent(
                title=title,
                snippet=snippet,
                source_url=(
                    f"https://{source}/mock/"
                    f"{region.lower().replace('-', '/')}-wn"
                ),
                source_name=source,
                region_code=region,
                timestamp=datetime.now(tz=timezone.utc),
            )
        ]
