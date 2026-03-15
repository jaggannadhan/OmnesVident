"""
NewsCatcherProvider — NewsCatcher Local News API integration.

Uses the geonames-based POST endpoint to surface hyper-local stories
for a given set of cities / subdivision.  Each city in `query_keywords`
becomes a geoname entry; the API returns news where any of those
locations is relevant (geonames_operator="OR").

Endpoint: https://local-news.newscatcherapi.com/api/latest_headlines/advanced
Auth:     x-api-token header
Docs:     https://newscatcherapi.com/news-api

Set NEWSCATCHER_API_KEY environment variable or pass api_key directly.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.core.normalizer import clean_and_truncate, strip_html
from ingestion_engine.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_LOCAL_NEWS_URL = "https://local-news.newscatcherapi.com/api/latest_headlines/advanced"

# Subdivision code → state/province name for richer geonames context
_SUB_TO_STATE: Dict[str, str] = {
    "IN-TN": "Tamil Nadu",      "IN-MH": "Maharashtra",
    "IN-DL": "Delhi",           "IN-KA": "Karnataka",
    "IN-WB": "West Bengal",     "IN-GJ": "Gujarat",
    "IN-RJ": "Rajasthan",       "IN-MP": "Madhya Pradesh",
    "IN-UP": "Uttar Pradesh",   "IN-AP": "Andhra Pradesh",
    "IN-TS": "Telangana",       "IN-KL": "Kerala",
    "IN-OR": "Odisha",          "IN-PB": "Punjab",
    "IN-HR": "Haryana",         "IN-BR": "Bihar",
    "IN-JH": "Jharkhand",       "IN-AS": "Assam",
    "IN-UK": "Uttarakhand",     "IN-HP": "Himachal Pradesh",
    "IN-CT": "Chhattisgarh",    "IN-JK": "Jammu and Kashmir",
    "US-CA": "California",      "US-TX": "Texas",
    "US-NY": "New York",        "US-FL": "Florida",
    "US-WA": "Washington",      "US-IL": "Illinois",
    "US-PA": "Pennsylvania",    "US-OH": "Ohio",
    "US-GA": "Georgia",         "US-NC": "North Carolina",
    "CA-ON": "Ontario",         "CA-BC": "British Columbia",
    "CA-QC": "Quebec",          "CA-AB": "Alberta",
    "AU-NSW": "New South Wales","AU-VIC": "Victoria",
    "AU-QLD": "Queensland",     "AU-WA": "Western Australia",
    "CN-BJ": "Beijing",         "CN-SH": "Shanghai",
    "CN-GD": "Guangdong",       "CN-SC": "Sichuan",
    "CN-HB": "Hubei",
    "BR-SP": "São Paulo",       "BR-RJ": "Rio de Janeiro",
    "BR-MG": "Minas Gerais",    "BR-CE": "Ceará",
    "BR-BA": "Bahia",
    "ZA-GT": "Gauteng",         "ZA-WC": "Western Cape",
    "ZA-KZN": "KwaZulu-Natal",
    "GB-ENG": "England",        "GB-SCT": "Scotland",
    "GB-WLS": "Wales",
}


class NewsCatcherProvider(BaseProvider):
    """
    Provider for NewsCatcher Local News API.

    Args:
        country:         ISO alpha-2 country code (e.g. "IN", "US").
        api_key:         NewsCatcher API key; falls back to NEWSCATCHER_API_KEY env var.
        subdivision:     ISO 3166-2 code (e.g. "IN-TN") — sets region_code on events.
        query_keywords:  City names to target (e.g. ["Chennai", "Madurai"]).
                         Each becomes a geoname entry.  If empty, country-level only.
        page_size:       Results per request (max 100). Default 100.
        when:            Recency window passed to the API (e.g. "1d", "7d"). Default "1d".
    """

    def __init__(
        self,
        country: str,
        api_key: Optional[str] = None,
        subdivision: Optional[str] = None,
        query_keywords: Optional[List[str]] = None,
        page_size: int = 100,
        when: str = "1d",
    ) -> None:
        self._country      = country.upper()
        self._api_key      = api_key or os.getenv("NEWSCATCHER_API_KEY", "MOCK_API_KEY")
        self._subdivision  = subdivision
        self._cities       = query_keywords or []
        self._page_size    = min(page_size, 100)
        self._when         = when

    @property
    def name(self) -> str:
        label = self._subdivision or self._country
        return f"NewsCatcher [{label}]"

    # ------------------------------------------------------------------
    # Build geonames payload
    # ------------------------------------------------------------------

    def _build_geonames(self) -> List[dict]:
        """
        Convert city list + optional subdivision into geonames array.

        Each city becomes:
          {"name": "Chennai", "country": "IN", "admin1": {"name": "Tamil Nadu"}}

        If no cities are provided, returns an empty list (country filter only).
        """
        state_name = _SUB_TO_STATE.get(self._subdivision or "", "")
        geonames: List[dict] = []
        for city in self._cities:
            entry: dict = {"name": city, "country": self._country}
            if state_name:
                entry["admin1"] = {"name": state_name}
            geonames.append(entry)
        return geonames

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(self) -> List[NewsEvent]:
        if self._api_key == "MOCK_API_KEY":
            logger.warning("%s: No API key — returning mock data.", self.name)
            return self._mock_events()

        geonames = self._build_geonames()

        payload: dict = {
            "when":        self._when,
            "lang":        ["en"],
            "countries":   [self._country],
            "page_size":   self._page_size,
            "is_paid_content": False,
        }
        if geonames:
            payload["geonames"] = geonames
            payload["geonames_operator"] = "OR"

        headers = {
            "Content-Type": "application/json",
            "x-api-token":  self._api_key,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(
                    _LOCAL_NEWS_URL, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "%s: HTTP %s — %s", self.name, exc.response.status_code, exc
                )
                return []
            except httpx.RequestError as exc:
                logger.error("%s: Request failed — %s", self.name, exc)
                return []

        articles = data.get("articles") or data.get("results") or []
        logger.info("%s: received %d articles.", self.name, len(articles))
        return self._parse(articles)

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def _parse(self, articles: list) -> List[NewsEvent]:
        region = self._subdivision or self._country
        events: List[NewsEvent] = []
        for article in articles:
            try:
                raw_text = (
                    article.get("excerpt")
                    or article.get("summary")
                    or article.get("content", "")
                )
                source_url = article.get("link") or article.get("url", "")
                source_name = (
                    article.get("clean_url")
                    or article.get("domain")
                    or article.get("source_url", self.name)
                )
                events.append(
                    NewsEvent(
                        title=strip_html(article.get("title", "")),
                        snippet=clean_and_truncate(raw_text),
                        source_url=source_url,
                        source_name=source_name,
                        region_code=region,
                        timestamp=self._parse_dt(
                            article.get("published_date")
                            or article.get("pub_date")
                        ),
                    )
                )
            except Exception as exc:
                logger.warning("%s: Skipping malformed article — %s", self.name, exc)
        return events

    @staticmethod
    def _parse_dt(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)

    # -----------------------------------------------------------------------
    # Mock data
    # -----------------------------------------------------------------------

    _SUBDIVISION_MOCK: Dict[str, tuple] = {
        "IN-TN": (
            "Chennai Metro Phase 3 tender awarded to L&T Construction",
            "Chennai Metropolitan Development Authority confirmed the ₹12,000 crore "
            "Phase 3 contract covering 9 new stations from Madhavaram to Sholinganallur.",
            "thehindu.com",
        ),
        "IN-MH": (
            "Mumbai Coastal Road opens southern stretch ahead of schedule",
            "Maharashtra PWD inaugurated the 4.5 km marine drive extension linking "
            "Worli to Haji Ali after monsoon repairs were completed two months early.",
            "hindustantimes.com",
        ),
        "IN-DL": (
            "Delhi odd-even scheme extended through February pollution surge",
            "DPCC data showed AQI exceeding 350 on six consecutive days; the transport "
            "ministry extended the vehicle rationing order by 10 days.",
            "ndtv.com",
        ),
        "IN-KA": (
            "Bengaluru water board approves Cauvery Stage 5 expansion",
            "BWSSB's board cleared the ₹5,550 crore project to supply an additional "
            "775 MLD to Bengaluru's rapidly expanding eastern zones.",
            "deccanherald.com",
        ),
        "IN-WB": (
            "Kolkata flyover collapse prompts emergency inspection of 28 bridges",
            "West Bengal PWD ordered a 72-hour structural audit after a minor span "
            "failure on the Ultadanga connector; no casualties reported.",
            "telegraphindia.com",
        ),
        "US-CA": (
            "Los Angeles county approves $1.2B wildfire recovery housing fund",
            "The LA Board of Supervisors voted 4-1 to establish a rapid-rehousing "
            "trust funded by developer impact fees and federal FEMA reimbursements.",
            "latimes.com",
        ),
        "US-TX": (
            "Houston Ship Channel reopens after chemical spill containment",
            "US Coast Guard lifted the navigation closure after Valero confirmed benzene "
            "levels fell below threshold; port traffic resumes with 48-hour vessel queue.",
            "houstonchronicle.com",
        ),
        "US-NY": (
            "New York MTA approves congestion pricing rollout date after court ruling",
            "A federal judge cleared the final injunction; MTA confirmed E-ZPass readers "
            "will go live on all Manhattan entry points from 60th Street southward.",
            "nytimes.com",
        ),
        "US-FL": (
            "Miami-Dade seawall upgrade secures $300M in federal climate funds",
            "FEMA's Hazard Mitigation Grant will reinforce 18 miles of Biscayne Bay "
            "shoreline, protecting 340,000 residents from storm surge.",
            "miamiherald.com",
        ),
        "US-WA": (
            "Seattle SR-99 tunnel reaches five-year safety milestone without incident",
            "WSDOT reported zero fatalities in the Battery Street tunnel replacement; "
            "average daily traffic has exceeded the pre-COVID baseline by 12%.",
            "seattletimes.com",
        ),
        "CN-BJ": (
            "Beijing launches AI-powered traffic management across ring roads",
            "The city's transport bureau activated 4,200 smart signal nodes on the "
            "3rd and 4th ring roads, cutting average peak-hour delays by 18%.",
            "chinadaily.com.cn",
        ),
        "CN-SH": (
            "Shanghai free-trade zone pilot expands cross-border data rules",
            "Regulators published draft rules allowing financial firms in the SFTZ to "
            "transfer customer data to overseas subsidiaries under new security review.",
            "shine.cn",
        ),
        "BR-SP": (
            "São Paulo metro Line 6 coral extension reaches final tunnelling stage",
            "ViaQuatro engineers broke through the last diaphragm wall at Brasilândia; "
            "the 15.3 km line is on track for a mid-2026 partial opening.",
            "folha.uol.com.br",
        ),
        "BR-RJ": (
            "Rio de Janeiro carnival sambadrome capacity raised after safety review",
            "RIOTUR confirmed the 2027 carnival will accommodate 72,000 spectators per "
            "night after new bleacher reinforcement passed federal fire-safety inspection.",
            "oglobo.globo.com",
        ),
        "ZA-GT": (
            "Johannesburg load-shedding drops to Stage 1 after Medupi unit returns",
            "Eskom confirmed unit 4 at Medupi power station resumed generation at full "
            "800 MW capacity, easing pressure on the Gauteng grid during peak demand.",
            "dailymaverick.co.za",
        ),
        "ZA-WC": (
            "Cape Town desalination plant doubles output after pump upgrade",
            "The City of Cape Town's Monwabisi facility now produces 14 ML/day following "
            "a R220 million pump replacement funded from the water resilience budget.",
            "groundup.org.za",
        ),
    }

    _GENERIC_MOCK_POOL = [
        (
            "Regional transport authority launches integrated ticketing pilot",
            "Commuters can now use a single contactless card across buses, metro and "
            "suburban rail under the new unified fare scheme covering the city core.",
            "regional-news.example.com",
        ),
        (
            "Local government approves 40 MW renewable energy micro-grid project",
            "The district council cleared planning permission for a solar-battery "
            "installation that will power 18,000 homes from 2027.",
            "local-press.example.com",
        ),
    ]

    def _mock_events(self) -> List[NewsEvent]:
        region = self._subdivision or self._country
        if self._subdivision and self._subdivision in self._SUBDIVISION_MOCK:
            title, snippet, source = self._SUBDIVISION_MOCK[self._subdivision]
            return [
                NewsEvent(
                    title=title,
                    snippet=snippet,
                    source_url=(
                        f"https://{source}/mock/"
                        f"{self._subdivision.lower().replace('-', '/')}-nc"
                    ),
                    source_name=source,
                    region_code=region,
                    timestamp=datetime.now(tz=timezone.utc),
                )
            ]
        offset = sum(ord(c) for c in region) % len(self._GENERIC_MOCK_POOL)
        title, snippet, source = self._GENERIC_MOCK_POOL[offset]
        return [
            NewsEvent(
                title=f"[{region}] {title}",
                snippet=snippet,
                source_url=f"https://{source}/mock/{region.lower()}-nc",
                source_name=source,
                region_code=region,
                timestamp=datetime.now(tz=timezone.utc),
            )
        ]
