from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_serializer

from ingestion_engine.core.models import NewsEvent


class EnrichedStory(BaseModel):
    """
    The output unit of the Intelligence Layer.

    One EnrichedStory represents a single logical news story, which may have
    been reported by several outlets. The highest-quality version is kept as
    `lead_event`; URLs from duplicate articles are stored in `secondary_sources`.
    """

    lead_event: NewsEvent
    secondary_sources: List[str] = []   # Duplicate article URLs

    category: str                        # One of the 8 canonical categories
    mentioned_regions: List[str] = []   # ISO alpha-2 codes found in the text

    dedup_group_id: str                  # Stable hash for the cluster
    processed_at: datetime

    # Geo-Intelligence (Module 6) — resolved by GeoResolver
    latitude: Optional[float] = None    # WGS84 decimal degrees
    longitude: Optional[float] = None   # WGS84 decimal degrees

    @field_serializer("processed_at")
    def serialize_processed_at(self, value: datetime) -> str:
        return value.isoformat()
