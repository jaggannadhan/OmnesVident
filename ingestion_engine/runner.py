"""
runner.py — Shared ingestion cycle logic.

Extracted from main.py so the same provider-build + IngestionManager logic
can be called from two entry points:

  1. python -m ingestion_engine.main   (CLI / local dev)
     → calls run_ingestion_cycle() then push_to_api(events)

  2. POST /tasks/ingest                (Cloud Run + Cloud Scheduler)
     → calls run_ingestion_cycle() then passes events directly to
       _process_and_store(), bypassing the HTTP round-trip.

No network calls or environment reads happen at import time; everything
is lazy-initialised inside run_ingestion_cycle().
"""

from __future__ import annotations

import logging
import os
import time
from typing import List

from ingestion_engine.core.manager import IngestionManager
from ingestion_engine.core.models import NewsEvent
from ingestion_engine.factory import ProviderFactory
from ingestion_engine.providers.newsdata_io import NewsDataProvider
from ingestion_engine.providers.reddit_provider import RedditProvider
from ingestion_engine.providers.rss_provider import RSSProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider configuration (shared constants — imported by main.py too)
# ---------------------------------------------------------------------------

NEWSDATA_COUNTRIES = [
    "us", "ca", "mx", "ar", "br",
    "gb", "de", "fr", "it", "ua",
    "jp", "cn", "in", "au", "kr",
    "il", "sa", "eg", "za", "ng",
]

ALWAYS_ON_SUBDIVISIONS = [
    "IN-TN", "IN-MH",
    "US-CA", "US-TX", "US-NY",
]

HIGH_RES_SUBDIVISIONS = [
    "US-FL", "US-WA",
    "IN-DL", "IN-KA", "IN-WB",
    "CN-BJ", "CN-SH", "CN-GD", "CN-SC", "CN-HB",
    "BR-SP", "BR-RJ", "BR-MG", "BR-CE", "BR-BA",
    "CA-ON", "CA-BC", "CA-QC", "CA-AB",
    "AU-NSW", "AU-VIC", "AU-QLD", "AU-WA",
    "ZA-GT", "ZA-WC", "ZA-KZN",
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

REDDIT_BUNDLES: list[dict] = [
    {"subreddits": ["Chennai", "TamilNadu", "chennaicity"],     "region_code": "IN-TN"},
    {"subreddits": ["mumbai", "Maharashtra", "pune"],            "region_code": "IN-MH"},
    {"subreddits": ["delhi", "newdelhi"],                        "region_code": "IN-DL"},
    {"subreddits": ["bangalore", "Karnataka"],                   "region_code": "IN-KA"},
    {"subreddits": ["kolkata", "WestBengal"],                    "region_code": "IN-WB"},
    {"subreddits": ["LosAngeles", "bayarea", "california"],     "region_code": "US-CA"},
    {"subreddits": ["houston", "Dallas", "texas"],              "region_code": "US-TX"},
    {"subreddits": ["nyc", "newyorkcity"],                       "region_code": "US-NY"},
    {"subreddits": ["Miami", "florida"],                         "region_code": "US-FL"},
    {"subreddits": ["Seattle", "washington"],                    "region_code": "US-WA"},
    {"subreddits": ["india"],                                    "region_code": "IN"},
    {"subreddits": ["usa", "politics"],                          "region_code": "US"},
    {"subreddits": ["canada"],                                   "region_code": "CA"},
    {"subreddits": ["australia"],                                "region_code": "AU"},
    {"subreddits": ["unitedkingdom", "london"],                  "region_code": "GB"},
    {"subreddits": ["germany"],                                  "region_code": "DE"},
    {"subreddits": ["france"],                                   "region_code": "FR"},
    {"subreddits": ["japan"],                                    "region_code": "JP"},
    {"subreddits": ["brasil"],                                   "region_code": "BR"},
    {"subreddits": ["southafrica"],                              "region_code": "ZA"},
    {"subreddits": ["worldnews", "geopolitics"],                "region_code": "WORLD"},
]


# ---------------------------------------------------------------------------
# Core function — call this from both main.py and /tasks/ingest
# ---------------------------------------------------------------------------

async def run_ingestion_cycle() -> List[NewsEvent]:
    """
    Build all providers, run a full ingestion cycle, and return raw events.

    The caller decides what to do with the events:
      • main.py        → push_to_api(events)  (HTTP POST to /ingest)
      • /tasks/ingest  → _process_and_store(events)  (in-process, no HTTP)
    """
    providers = []
    always_on = []
    sub_national = []

    # ── Country-level NewsData.io baseline ───────────────────────────────────
    for country in NEWSDATA_COUNTRIES:
        providers.append(NewsDataProvider(country=country))

    for sub in ALWAYS_ON_SUBDIVISIONS:
        country = sub.split("-")[0].lower()
        always_on.append(NewsDataProvider(country=country, subdivision=sub))

    for sub in HIGH_RES_SUBDIVISIONS:
        country = sub.split("-")[0].lower()
        sub_national.append(NewsDataProvider(country=country, subdivision=sub))

    # ── RSS ──────────────────────────────────────────────────────────────────
    for feed_config in RSS_FEEDS:
        providers.append(
            RSSProvider(
                feed_urls=feed_config["urls"],
                region_code=feed_config["region_code"],
            )
        )

    # ── Reddit ───────────────────────────────────────────────────────────────
    reddit_agent = os.getenv(
        "REDDIT_USER_AGENT",
        "OmnesVident:news-ingestion:v1.0 (by /u/omnesvident_bot)",
    )
    for bundle in REDDIT_BUNDLES:
        providers.append(
            RedditProvider(
                subreddits=bundle["subreddits"],
                region_code=bundle["region_code"],
                user_agent=reddit_agent,
            )
        )

    # ── Module 10.0 specialist providers (Currents / WorldNews / Mediastack / GNews) ─
    factory = ProviderFactory()
    specialist_providers = factory.build_all()
    providers.extend(specialist_providers)
    logger.info(
        "ProviderFactory: %d specialist provider(s) (budget: %s).",
        len(specialist_providers),
        {k: f"{v['remaining']}/{v['capacity']}" for k, v in factory.scheduler.summary().items()},
    )

    # ── Run ──────────────────────────────────────────────────────────────────
    cycle = int(time.time()) // 300

    manager = IngestionManager(providers=providers)
    events = await manager.run(
        always_on=always_on,
        sub_national=sub_national,
        batch_size=6,
        cycle=cycle,
    )

    logger.info("run_ingestion_cycle: collected %d raw events.", len(events))

    # ── Firestore raw buffer (Module 12.0) — fire-and-forget ─────────────────
    # Push raw events to raw_ingestion_buffer so the Refiner can promote them
    # to master_news asynchronously.  Gracefully skipped if FIRESTORE_PROJECT
    # is not set (local dev / SQLite-only mode).
    try:
        from database.firestore_manager import firestore_manager
        if firestore_manager._is_enabled() and events:
            written = await firestore_manager.push_to_raw(events, provider_id="ingestion_engine")
            logger.info("run_ingestion_cycle: %d events written to raw_ingestion_buffer.", written)
    except Exception as exc:
        logger.warning("run_ingestion_cycle: Firestore push skipped — %s", exc)

    return events
