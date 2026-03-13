"""
Entry point for the Ingestion Engine.

Run with:
    python -m ingestion_engine.main

Environment variables:
    NEWSDATA_API_KEY  — API key for newsdata.io (falls back to mock data if absent)
    API_BASE_URL      — Base URL of the FastAPI backend (default: http://127.0.0.1:8000)
"""

import asyncio
import json
import logging
import os

import httpx

from ingestion_engine.core.manager import IngestionManager
from ingestion_engine.providers.newsdata_io import NewsDataProvider
from ingestion_engine.providers.rss_provider import RSSProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------
# Matches every region shown in the frontend sidebar
NEWSDATA_COUNTRIES = [
    "us", "ca", "mx", "ar", "br",          # Americas
    "gb", "de", "fr", "it", "ua",          # Europe
    "jp", "cn", "in", "au", "kr",          # Asia-Pacific
    "il", "sa", "eg", "za", "ng",          # Middle East & Africa
]

RSS_FEEDS = [
    {
        "urls": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/technology/rss.xml",
        ],
        "region_code": "GB",
    },
    {
        "urls": ["https://rss.nytimes.com/services/xml/rss/nyt/World.xml"],
        "region_code": "US",
    },
]


async def push_to_api(events) -> None:
    """POST collected events to the FastAPI /ingest endpoint."""
    payload = {
        "events": [e.model_dump(mode="json") for e in events]
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(f"{API_BASE_URL}/ingest", json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("API accepted %d event(s): %s", data.get("accepted", "?"), data.get("message", ""))
        except httpx.HTTPStatusError as exc:
            logger.error("API returned HTTP %s — %s", exc.response.status_code, exc.response.text)
        except httpx.RequestError as exc:
            logger.error("Could not reach API at %s — %s", API_BASE_URL, exc)


async def main() -> None:
    providers = []

    for country in NEWSDATA_COUNTRIES:
        providers.append(NewsDataProvider(country=country))

    for feed_config in RSS_FEEDS:
        providers.append(
            RSSProvider(
                feed_urls=feed_config["urls"],
                region_code=feed_config["region_code"],
            )
        )

    manager = IngestionManager(providers=providers)
    events = await manager.run()

    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE — {len(events)} events collected")
    print(f"{'='*60}\n")

    if not events:
        logger.warning("No events collected — nothing to push.")
        return

    await push_to_api(events)


if __name__ == "__main__":
    asyncio.run(main())
