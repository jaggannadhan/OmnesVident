"""
FastAPI request/response schemas.

Kept separate from ORM models (database.py) and domain models
(ingestion_engine/intelligence_layer) to preserve a clean API boundary.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Ingest (POST /ingest)
# ---------------------------------------------------------------------------

class NewsEventIn(BaseModel):
    """Wire representation of a NewsEvent from the Ingestion Engine."""
    title: str
    snippet: str
    source_url: str
    source_name: str
    region_code: str
    timestamp: datetime


class IngestRequest(BaseModel):
    events: List[NewsEventIn] = Field(..., min_length=1)


class IngestResponse(BaseModel):
    accepted: int           # Total events received
    queued: bool = True     # Processing happens in background
    message: str = "Batch accepted for processing."


# ---------------------------------------------------------------------------
# News retrieval (GET /news, GET /news/{region_code})
# ---------------------------------------------------------------------------

class StoryOut(BaseModel):
    """API response shape for a single enriched story."""
    dedup_group_id: str
    title: str
    snippet: str
    source_url: str
    source_name: str
    region_code: str
    category: str
    mentioned_regions: List[str]
    secondary_sources: List[str]
    timestamp: datetime
    processed_at: datetime

    model_config = {"from_attributes": True}


class PaginatedStoriesResponse(BaseModel):
    total: int
    offset: int
    limit: int
    stories: List[StoryOut]
