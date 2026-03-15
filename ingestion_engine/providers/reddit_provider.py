"""
RedditProvider — unauthenticated read-only Reddit ingestion via asyncpraw.

Bundles geographically-related subreddits into a single combined feed using
Reddit's '+' operator (e.g. 'Chennai+TamilNadu+chennaicity').  A
SUBREDDIT_TO_REGION mapping re-assigns each post's region_code based on the
subreddit it came from, giving hyper-local geographic precision.

Install:  pip install asyncpraw
Env var:  REDDIT_USER_AGENT  (optional, defaults to a safe generic value)

Unauthenticated access is read-only and subject to Reddit's public rate
limits (~60 req/min).  An asyncio.sleep guard prevents runaway polling.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.core.normalizer import clean_and_truncate, strip_html
from ingestion_engine.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Subreddit → ISO 3166-2 region_code mapping
# Adding a new region is as simple as adding a row here and to REDDIT_BUNDLES
# in main.py.
# ---------------------------------------------------------------------------
SUBREDDIT_TO_REGION: Dict[str, str] = {
    # India — states & cities
    "Chennai":          "IN-TN",
    "TamilNadu":        "IN-TN",
    "chennaicity":      "IN-TN",
    "mumbai":           "IN-MH",
    "Maharashtra":      "IN-MH",
    "pune":             "IN-MH",
    "delhi":            "IN-DL",
    "newdelhi":         "IN-DL",
    "bangalore":        "IN-KA",
    "Karnataka":        "IN-KA",
    "kolkata":          "IN-WB",
    "WestBengal":       "IN-WB",
    "india":            "IN",
    # United States
    "LosAngeles":       "US-CA",
    "bayarea":          "US-CA",
    "california":       "US-CA",
    "houston":          "US-TX",
    "Dallas":           "US-TX",
    "texas":            "US-TX",
    "nyc":              "US-NY",
    "newyorkcity":      "US-NY",
    "Miami":            "US-FL",
    "florida":          "US-FL",
    "Seattle":          "US-WA",
    "washington":       "US-WA",
    "usa":              "US",
    "politics":         "US",
    # China
    "beijing":          "CN-BJ",
    "shanghai":         "CN-SH",
    "china":            "CN",
    # Brazil
    "saopaulo":         "BR-SP",
    "riodejaneiro":     "BR-RJ",
    "brasil":           "BR",
    # Canada
    "toronto":          "CA-ON",
    "ontario":          "CA-ON",
    "vancouver":        "CA-BC",
    "britishcolumbia":  "CA-BC",
    "canada":           "CA",
    # Australia
    "sydney":           "AU-NSW",
    "melbourne":        "AU-VIC",
    "australia":        "AU",
    # South Africa
    "johannesburg":     "ZA-GT",
    "capetown":         "ZA-WC",
    "southafrica":      "ZA",
    # UK
    "unitedkingdom":    "GB",
    "london":           "GB",
    # Germany
    "germany":          "DE",
    # France
    "france":           "FR",
    # Japan
    "japan":            "JP",
    # Global / fallback
    "worldnews":        "WORLD",
    "news":             "WORLD",
    "geopolitics":      "WORLD",
    "technology":       "WORLD",
}

# Default region when subreddit not in the map
_DEFAULT_REGION = "WORLD"

# Minimum seconds between successive fetch() calls on the same provider
# instance — guards against runaway polling.
_MIN_FETCH_INTERVAL: float = 10.0


class RedditProvider(BaseProvider):
    """
    Unauthenticated read-only Reddit provider.

    Args:
        subreddits:  List of subreddit names to bundle (e.g. ['Chennai', 'TamilNadu']).
                     They are joined with '+' for a single combined stream.
        limit:       Max posts to fetch per cycle (default 25, Reddit max 100).
        sort:        Feed sort — 'new' (default), 'hot', or 'top'.
        user_agent:  HTTP User-Agent string for the Reddit API.
        region_code: Fallback region when a subreddit is not in SUBREDDIT_TO_REGION.
    """

    def __init__(
        self,
        subreddits: List[str],
        limit: int = 25,
        sort: str = "new",
        user_agent: Optional[str] = None,
        region_code: str = _DEFAULT_REGION,
    ) -> None:
        if not subreddits:
            raise ValueError("At least one subreddit name is required.")
        self._subreddits = subreddits
        self._combined = "+".join(subreddits)
        self._limit = min(limit, 100)
        self._sort = sort if sort in ("new", "hot", "top") else "new"
        self._user_agent = (
            user_agent
            or os.getenv("REDDIT_USER_AGENT", "OmnesVident:news-ingestion:v1.0 (by /u/omnesvident_bot)")
        )
        self._default_region = region_code
        self._last_fetch_at: float = 0.0

    @property
    def name(self) -> str:
        return f"Reddit [r/{self._combined}]"

    async def fetch(self) -> List[NewsEvent]:
        # Rate-limit guard — enforce minimum interval between fetches
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_fetch_at
        if elapsed < _MIN_FETCH_INTERVAL:
            wait = _MIN_FETCH_INTERVAL - elapsed
            logger.debug("%s: Rate-limit guard — sleeping %.1fs.", self.name, wait)
            await asyncio.sleep(wait)

        try:
            import asyncpraw  # noqa: PLC0415 — optional dependency
        except ImportError:
            logger.error(
                "%s: asyncpraw is not installed. Run: pip install asyncpraw", self.name
            )
            return []

        events: List[NewsEvent] = []
        try:
            async with asyncpraw.Reddit(
                client_id="",
                client_secret="",
                user_agent=self._user_agent,
            ) as reddit:
                subreddit = await reddit.subreddit(self._combined)
                feed = getattr(subreddit, self._sort)
                async for post in feed(limit=self._limit):
                    event = self._post_to_event(post)
                    if event:
                        events.append(event)
        except Exception as exc:
            logger.error("%s: Fetch failed — %s", self.name, exc)

        self._last_fetch_at = asyncio.get_event_loop().time()
        logger.info("%s: Fetched %d post(s).", self.name, len(events))
        return events

    def _post_to_event(self, post) -> Optional[NewsEvent]:
        try:
            # Determine region from originating subreddit
            sub_name: str = post.subreddit.display_name
            region = SUBREDDIT_TO_REGION.get(sub_name, self._default_region)

            title = strip_html(post.title or "")
            if not title:
                return None

            # selftext for text posts; empty string for link posts
            raw_body = post.selftext or ""
            snippet = clean_and_truncate(raw_body) if raw_body.strip() else title[:300]

            source_url = post.url or f"https://reddit.com{post.permalink}"
            source_name = f"reddit.com/r/{sub_name}"

            timestamp = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)

            return NewsEvent(
                title=title,
                snippet=snippet,
                source_url=source_url,
                source_name=source_name,
                region_code=region,
                timestamp=timestamp,
            )
        except Exception as exc:
            logger.warning("%s: Skipping post — %s", self.name, exc)
            return None
