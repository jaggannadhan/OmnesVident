"""
Entry point for the Ingestion Engine (local / CLI mode).

Run with:
    python -m ingestion_engine.main

In Cloud Run the ingestion is triggered via POST /tasks/ingest instead of
this script.  Provider configuration lives in ingestion_engine/runner.py
so both entry points share the same logic.

Environment variables:
    NEWSDATA_API_KEY         — API key for newsdata.io (falls back to mock data if absent)
    NEWSCATCHER_API_KEY      — API key for NewsCatcher (falls back to mock data if absent)
    CURRENTS_NEW_API         — API key for Currents API (US/CA/MX; 600 req/month)
    WORLD_NEWS_API_KEY       — API key for World News API (India; 1,500 req/month)
    MEDIA_STACK_NEWS_API_KEY — API key for Mediastack (EU/UK; 500 req/month)
    GNEWS_API                — API key for GNews (US/CA supplement; 100 req/day)
    REDDIT_USER_AGENT        — User-Agent string for Reddit API (unauthenticated; optional)
    API_BASE_URL             — Base URL of the FastAPI backend (default: http://127.0.0.1:8000)
"""

import asyncio
import logging
import os

import httpx

from ingestion_engine.runner import run_ingestion_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


async def push_to_api(events) -> None:
    """POST collected events to the FastAPI /ingest endpoint."""
    payload = {"events": [e.model_dump(mode="json") for e in events]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(f"{API_BASE_URL}/ingest", json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "API accepted %d event(s): %s",
                data.get("accepted", "?"),
                data.get("message", ""),
            )
        except httpx.HTTPStatusError as exc:
            logger.error("API returned HTTP %s — %s", exc.response.status_code, exc.response.text)
        except httpx.RequestError as exc:
            logger.error("Could not reach API at %s — %s", API_BASE_URL, exc)


async def main() -> None:
    events = await run_ingestion_cycle()

    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE — {len(events)} events collected")
    print(f"{'='*60}\n")

    if not events:
        logger.warning("No events collected — nothing to push.")
        return

    await push_to_api(events)


if __name__ == "__main__":
    asyncio.run(main())
