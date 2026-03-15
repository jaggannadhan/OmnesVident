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
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
# CORS — allow the Vercel frontend (and localhost dev) to call the API.
# CORS_ORIGINS env var overrides defaults; separate multiple origins with ","
# ---------------------------------------------------------------------------
_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "https://omnes-vident.vercel.app,http://localhost:5173,http://localhost:3000",
)
_cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://omnes-vident.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
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
        latitude=record.latitude,
        longitude=record.longitude,
    )


# ---------------------------------------------------------------------------
# Firestore helpers
# ---------------------------------------------------------------------------

def _firestore_doc_to_story_out(doc: Dict[str, Any]) -> StoryOut:
    """Map a raw Firestore master_news document to a StoryOut schema."""
    ts = doc.get("timestamp")
    if ts is None:
        ts = datetime.now(tz=timezone.utc)
    elif not ts.tzinfo:
        ts = ts.replace(tzinfo=timezone.utc)

    promoted = doc.get("promoted_at") or ts
    if not promoted.tzinfo:
        promoted = promoted.replace(tzinfo=timezone.utc)

    return StoryOut(
        dedup_group_id=doc.get("_doc_id", ""),
        title=doc.get("title", ""),
        snippet=doc.get("snippet", ""),
        source_url=doc.get("source_url", ""),
        source_name=doc.get("source_name", ""),
        region_code=doc.get("region_code", ""),
        category=doc.get("category", "WORLD"),
        mentioned_regions=doc.get("mentioned_regions") or [],
        secondary_sources=doc.get("secondary_sources") or [],
        timestamp=ts,
        processed_at=promoted,
        latitude=doc.get("latitude"),
        longitude=doc.get("longitude"),
    )


async def _query_firestore(
    region: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    limit: int,
    offset: int,
) -> Optional[PaginatedStoriesResponse]:
    """
    Try to serve the request from Firestore master_news.

    Returns None if Firestore is disabled or the query fails, so the caller
    can fall back to SQLite.
    """
    try:
        from database.firestore_manager import firestore_manager
        if not firestore_manager._is_enabled():
            return None

        docs = await firestore_manager.query_master_by_timestamp(
            region_code=region,
            start_dt=start_date,
            end_dt=end_date,
            limit=limit,
            offset=offset,
        )
        stories = [_firestore_doc_to_story_out(d) for d in docs]
        # Firestore doesn't give us an exact total cheaply; use len + offset as estimate
        total = offset + len(stories) + (1 if len(stories) == limit else 0)
        return PaginatedStoriesResponse(
            total=total, offset=offset, limit=limit, stories=stories
        )
    except Exception as exc:
        logger.warning("_query_firestore: failed, will fall back to SQLite — %s", exc)
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/news/coverage", tags=["News"])
async def news_coverage():
    """
    Return the oldest/newest timestamps in Firestore master_news plus total count.
    The frontend uses this to grey out time-range presets outside the data window.
    Falls back gracefully when Firestore is unavailable.
    """
    try:
        from database.firestore_manager import firestore_manager
        if firestore_manager._is_enabled():
            cov = await firestore_manager.get_coverage()
            return {
                "oldest": cov["oldest"].isoformat() if cov["oldest"] else None,
                "newest": cov["newest"].isoformat() if cov["newest"] else None,
                "total": cov["total"],
                "source": "firestore",
            }
    except Exception as exc:
        logger.warning("news_coverage: Firestore unavailable — %s", exc)
    return {"oldest": None, "newest": None, "total": -1, "source": "unavailable"}


@app.get("/news", response_model=PaginatedStoriesResponse, tags=["News"])
async def list_news(
    region: Optional[str] = Query(None, description="ISO alpha-2 region filter"),
    category: Optional[str] = Query(None, description="Category filter (e.g. POLITICS)"),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    start_date: Optional[datetime] = Query(None, description="ISO 8601 — filter stories on or after this timestamp"),
    end_date: Optional[datetime] = Query(None, description="ISO 8601 — filter stories on or before this timestamp"),
    session: Session = Depends(get_db_session),
):
    """
    Return a paginated list of enriched stories with optional filters.

    When start_date/end_date are provided (or Firestore is enabled), queries
    Firestore master_news for persistent cross-restart results.  Falls back to
    SQLite when Firestore is unavailable.  Defaults to the last 24 hours if no
    date filters are supplied.
    """
    # Default window: last 24 hours (keeps the globe populated on first load)
    effective_start = start_date or (datetime.now(tz=timezone.utc) - timedelta(hours=24))
    effective_end = end_date  # None = no upper bound

    # Try Firestore first (persistent, survives container restarts)
    fs_result = await _query_firestore(
        region=region,
        start_date=effective_start,
        end_date=effective_end,
        limit=limit,
        offset=offset,
    )
    if fs_result is not None and fs_result.stories:
        return fs_result

    # Fall back to SQLite
    stories, total = get_latest_news(
        session,
        region=region,
        category=category,
        limit=limit,
        offset=offset,
        start_date=effective_start,
        end_date=effective_end,
    )
    return PaginatedStoriesResponse(
        total=total,
        offset=offset,
        limit=limit,
        stories=[_to_story_out(s) for s in stories],
    )


@app.get("/news/{region_code}", response_model=PaginatedStoriesResponse, tags=["News"])
async def list_news_by_region(
    region_code: str,
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    start_date: Optional[datetime] = Query(None, description="ISO 8601 — filter stories on or after this timestamp"),
    end_date: Optional[datetime] = Query(None, description="ISO 8601 — filter stories on or before this timestamp"),
    session: Session = Depends(get_db_session),
):
    """Return stories for a specific ISO alpha-2 region (primary + cross-regional)."""
    if len(region_code) != 2:
        raise HTTPException(status_code=422, detail="region_code must be ISO alpha-2 (2 chars).")

    effective_start = start_date or (datetime.now(tz=timezone.utc) - timedelta(hours=24))
    effective_end = end_date

    fs_result = await _query_firestore(
        region=region_code.upper(),
        start_date=effective_start,
        end_date=effective_end,
        limit=limit,
        offset=offset,
    )
    if fs_result is not None and fs_result.stories:
        return fs_result

    stories, total = get_latest_news(
        session,
        region=region_code.upper(),
        category=category,
        limit=limit,
        offset=offset,
        start_date=effective_start,
        end_date=effective_end,
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


# ---------------------------------------------------------------------------
# Cloud Scheduler heartbeat — POST /tasks/ingest
# ---------------------------------------------------------------------------

# Set INGEST_SECRET in Cloud Run env vars; Cloud Scheduler sends it as
# X-Ingest-Token header.  If the env var is unset the endpoint is disabled.
_INGEST_SECRET = os.getenv("INGEST_SECRET", "")


@app.post("/tasks/ingest", status_code=202, tags=["Tasks"])
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    x_ingest_token: Optional[str] = Header(default=None),
):
    """
    Triggered by Cloud Scheduler every 15 minutes.

    Security: validates the X-Ingest-Token header against the INGEST_SECRET
    environment variable.  Returns 403 if the secret is missing or wrong.
    Returns 503 if INGEST_SECRET is not configured (endpoint disabled).

    The ingestion cycle runs in a BackgroundTask so this endpoint returns
    202 immediately.  Events are processed in-process — no HTTP round-trip
    to /ingest needed.
    """
    if not _INGEST_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Ingestion endpoint not configured (INGEST_SECRET not set).",
        )
    if x_ingest_token != _INGEST_SECRET:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Ingest-Token.")

    async def _run() -> None:
        try:
            from ingestion_engine.runner import run_ingestion_cycle
            events = await run_ingestion_cycle()
            if not events:
                logger.warning("/tasks/ingest: ingestion cycle produced no events.")
                return

            # 1. SQLite pipeline — always runs (primary store)
            await _process_and_store(events)
            logger.info("/tasks/ingest: SQLite pipeline processed %d event(s).", len(events))

            # 2. Firestore Refiner — runs after raw buffer push (done in runner.py)
            #    Promotes pending raw docs to master_news with subdivision tagging.
            try:
                from tasks.refiner import refiner
                promoted = await refiner.refine_pending(limit=200)
                if promoted:
                    logger.info("/tasks/ingest: Refiner promoted %d doc(s) to master_news.", promoted)
            except Exception as ref_exc:
                logger.warning("/tasks/ingest: Refiner skipped — %s", ref_exc)

        except Exception as exc:
            logger.error("/tasks/ingest: unhandled error — %s", exc, exc_info=True)

    background_tasks.add_task(_run)
    return {"status": "accepted", "message": "Ingestion cycle queued."}
