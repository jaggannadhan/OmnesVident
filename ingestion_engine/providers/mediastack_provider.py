"""
MediastackProvider — Mediastack API integration for European and UK coverage.

Free tier: 500 requests/month  →  budget-gated via RequestScheduler.
Docs: https://mediastack.com/documentation

Auth: access_key query param
Env:  MEDIASTACK_API_KEY

Note: Free tier uses HTTP (not HTTPS).  Upgrade to paid for HTTPS.
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

# Free tier HTTP; swap to https:// on paid plan
_MEDIASTACK_BASE = "http://api.mediastack.com/v1/news"

# Mediastack country code → ISO 3166-2 region_code mapping
_MEDIASTACK_COUNTRY_TO_REGION: Dict[str, str] = {
    "gb": "GB",
    "de": "DE",
    "fr": "FR",
    "it": "IT",
    "ua": "UA",
    "es": "ES",
    "nl": "NL",
    "pl": "PL",
    "se": "SE",
    "no": "NO",
    "dk": "DK",
    "fi": "FI",
    "pt": "PT",
    "be": "BE",
    "at": "AT",
    "ch": "CH",
    "cz": "CZ",
    "hu": "HU",
    "ro": "RO",
    "gr": "GR",
}


class MediastackProvider(BaseProvider):
    """
    Provider backed by Mediastack API for European news coverage.

    Args:
        countries:  List of Mediastack country codes (e.g. ["gb", "de", "fr"]).
        languages:  List of language codes (default ["en"]).
        limit:      Results per request (1-100). Default 25.
        api_key:    Falls back to MEDIASTACK_API_KEY env var.
        scheduler:  Optional RequestScheduler for budget enforcement.
    """

    def __init__(
        self,
        countries: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        limit: int = 25,
        api_key: Optional[str] = None,
        scheduler: Optional["RequestScheduler"] = None,
    ) -> None:
        self._countries = [c.lower() for c in (countries or ["gb", "de", "fr", "it"])]
        self._languages = languages or ["en"]
        self._limit = min(limit, 100)
        self._api_key = api_key or os.getenv("MEDIA_STACK_NEWS_API_KEY", "MOCK_API_KEY")
        self._scheduler = scheduler

    @property
    def name(self) -> str:
        label = ",".join(c.upper() for c in self._countries)
        return f"Mediastack [{label}]"

    async def fetch(self) -> List[NewsEvent]:
        if self._api_key == "MOCK_API_KEY":
            logger.warning("%s: No API key — returning mock data.", self.name)
            return self._mock_events()

        if self._scheduler and not self._scheduler.consume("mediastack"):
            logger.warning(
                "%s: Monthly quota exhausted — returning mock data as fallback.", self.name
            )
            return self._mock_events()

        params = {
            "access_key": self._api_key,
            "countries":  ",".join(self._countries),
            "languages":  ",".join(self._languages),
            "limit":      self._limit,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(_MEDIASTACK_BASE, params=params)
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
        for article in data.get("data", []):
            try:
                country_code = (article.get("country") or "").lower()
                region = _MEDIASTACK_COUNTRY_TO_REGION.get(
                    country_code, country_code.upper() or "EU"
                )
                events.append(
                    NewsEvent(
                        title=strip_html(article.get("title", "")),
                        snippet=clean_and_truncate(article.get("description") or ""),
                        source_url=article.get("url", ""),
                        source_name=article.get("source", self.name),
                        region_code=region,
                        timestamp=self._parse_dt(article.get("published_at")),
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
    # Mock data — one story per covered European country

    _COUNTRY_MOCK: Dict[str, tuple] = {
        "gb": (
            "UK Chancellor unveils £40B growth package targeting green manufacturing",
            "The Autumn Statement allocates funds to battery gigafactories in the North "
            "East and Wales, with a new apprenticeship levy exemption for under-25s.",
            "bbc.co.uk",
        ),
        "de": (
            "Germany approves 50 GW offshore wind expansion in North Sea by 2035",
            "The Bundestag passed the revised Offshore Wind Energy Act with broad coalition "
            "support; four new wind farm zones will be auctioned in the first phase.",
            "spiegel.de",
        ),
        "fr": (
            "Paris 2024 Olympics legacy fund redirected to Seine river cleanup programme",
            "The €800M urban renewal allocation now targets riverbank dredging and "
            "wastewater treatment upgrades affecting 2.2 million Île-de-France residents.",
            "lemonde.fr",
        ),
        "it": (
            "Italy fast-tracks high-speed rail corridor linking Turin to Naples",
            "The €14B TAV expansion will cut Rome–Milan journey time to 90 minutes; "
            "the southern extension to Reggio Calabria breaks ground next quarter.",
            "corriere.it",
        ),
        "ua": (
            "Ukraine receives first tranche of EU reconstruction fund for infrastructure",
            "The €8B disbursement from the Ukraine Facility covers bridge, road, and "
            "power grid restoration; Kyiv commits to anti-corruption oversight mechanisms.",
            "kyivindependent.com",
        ),
    }

    _FALLBACK_MOCK: tuple = (
        "European Central Bank trims deposit rate by 25 basis points",
        "The ECB Governing Council cited subdued eurozone growth and falling energy "
        "import costs; all major bond markets rallied on the decision.",
        "ft.com",
    )

    def _mock_events(self) -> List[NewsEvent]:
        events: List[NewsEvent] = []
        for country_code in self._countries:
            title, snippet, source = self._COUNTRY_MOCK.get(
                country_code, self._FALLBACK_MOCK
            )
            region = _MEDIASTACK_COUNTRY_TO_REGION.get(
                country_code, country_code.upper()
            )
            events.append(
                NewsEvent(
                    title=title,
                    snippet=snippet,
                    source_url=f"https://{source}/mock/{country_code}-ms",
                    source_name=source,
                    region_code=region,
                    timestamp=datetime.now(tz=timezone.utc),
                )
            )
        return events
