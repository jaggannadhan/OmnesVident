"""
FastAPI application and route definitions.

Endpoints:
  GET  /news                  — Paginated global stories (optional filters)
  GET  /news/{region_code}    — Stories for a specific ISO region
  POST /ingest                — Internal: push a batch of NewsEvents for processing

The Intelligence Pipeline is CPU-bound; it runs in a thread-pool executor
(via BackgroundTasks + run_in_executor) so the API stays responsive.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from api_storage.database import create_db_and_tables, get_db_session
from api_storage.repository import (
    cleanup_old_seen_stories,
    get_latest_news,
    get_seen_group_ids,
    save_stories,
)
from api_storage.schemas import (
    IngestRequest,
    IngestResponse,
    PaginatedStoriesResponse,
    StoryOut,
)
from ingestion_engine.core.models import NewsEvent
from intelligence_layer.pipeline import IntelligencePipeline

logger = logging.getLogger(__name__)

_pipeline = IntelligencePipeline()


# ---------------------------------------------------------------------------
# Lifespan: DB init + startup cleanup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    # Purge stale seen-story entries on every cold start
    from api_storage.database import get_session
    with get_session() as session:
        removed = cleanup_old_seen_stories(session, older_than_hours=48)
        if removed:
            logger.info("Startup cleanup: removed %d stale SeenStory rows.", removed)
    yield


app = FastAPI(
    title="OmnesVident News API",
    description="Real-time global news discovery — storage and retrieval layer.",
    version="0.3.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Background processing helper
# ---------------------------------------------------------------------------

async def _process_and_store(raw_events: List[NewsEvent]) -> None:
    """
    Run the Intelligence Pipeline in a thread-pool executor, then persist
    results.  Called via FastAPI BackgroundTasks so the POST /ingest response
    is returned immediately (202 Accepted).
    """
    loop = asyncio.get_running_loop()

    try:
        # 1. Run the sync pipeline off the event loop
        enriched = await loop.run_in_executor(None, _pipeline.process, raw_events)

        if not enriched:
            logger.info("_process_and_store: Pipeline produced no stories.")
            return

        # 2. Persist (upsert/merge)
        from api_storage.database import get_session
        with get_session() as session:
            # Opportunistic cleanup before each ingest
            cleanup_old_seen_stories(session, older_than_hours=48)
            inserted, merged = save_stories(session, enriched)
            logger.info(
                "_process_and_store: %d inserted, %d merged from %d raw events.",
                inserted, merged, len(raw_events),
            )

    except Exception as exc:
        logger.error("_process_and_store: Unhandled error — %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Helper: build StoryOut from ORM record
# ---------------------------------------------------------------------------

def _to_story_out(record) -> StoryOut:
    return StoryOut(
        dedup_group_id=record.dedup_group_id,
        title=record.title,
        snippet=record.snippet,
        source_url=record.source_url,
        source_name=record.source_name,
        region_code=record.region_code,
        category=record.category,
        mentioned_regions=record.mentioned_regions,
        secondary_sources=record.secondary_sources,
        timestamp=record.timestamp,
        processed_at=record.processed_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/news", response_model=PaginatedStoriesResponse, tags=["News"])
def list_news(
    region: Optional[str] = Query(None, description="ISO alpha-2 region filter"),
    category: Optional[str] = Query(None, description="Category filter (e.g. POLITICS)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db_session),
):
    """Return a paginated list of enriched stories with optional filters."""
    stories, total = get_latest_news(
        session, region=region, category=category, limit=limit, offset=offset
    )
    return PaginatedStoriesResponse(
        total=total,
        offset=offset,
        limit=limit,
        stories=[_to_story_out(s) for s in stories],
    )


@app.get("/news/{region_code}", response_model=PaginatedStoriesResponse, tags=["News"])
def list_news_by_region(
    region_code: str,
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db_session),
):
    """Return stories for a specific ISO alpha-2 region (primary + cross-regional)."""
    if len(region_code) != 2:
        raise HTTPException(status_code=422, detail="region_code must be ISO alpha-2 (2 chars).")
    stories, total = get_latest_news(
        session,
        region=region_code.upper(),
        category=category,
        limit=limit,
        offset=offset,
    )
    return PaginatedStoriesResponse(
        total=total,
        offset=offset,
        limit=limit,
        stories=[_to_story_out(s) for s in stories],
    )


@app.post("/ingest", response_model=IngestResponse, status_code=202, tags=["Internal"])
async def ingest_events(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
):
    """
    Accept a batch of raw NewsEvents from the Ingestion Engine.

    Filters out events whose dedup_group_id was already seen in the last 24
    hours before dispatching to the Intelligence Pipeline.  Processing is
    async (BackgroundTasks); this endpoint always returns 202 immediately.
    """
    # Convert wire schema → domain model
    raw_events: List[NewsEvent] = [
        NewsEvent(**e.model_dump()) for e in payload.events
    ]

    # Pre-filter using the stateful SeenStories table (resolves Module 2 debt)
    seen_ids = get_seen_group_ids(session, since_hours=24)
    if seen_ids:
        from intelligence_layer.deduplicator import _group_id
        raw_events = [
            e for e in raw_events
            if _group_id(e.title, e.region_code) not in seen_ids
        ]
        logger.info(
            "/ingest: %d events after pre-filtering %d already-seen group IDs.",
            len(raw_events), len(seen_ids),
        )

    if not raw_events:
        return IngestResponse(accepted=0, message="All events already seen within 24 hours.")

    background_tasks.add_task(_process_and_store, raw_events)

    return IngestResponse(
        accepted=len(raw_events),
        message=f"{len(raw_events)} event(s) queued for processing.",
    )


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "version": app.version}
