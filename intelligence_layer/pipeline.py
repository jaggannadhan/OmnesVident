"""
IntelligencePipeline — chains tagging → deduplication → classification → geo-enrichment.

Input:  List[NewsEvent]   (raw output from IngestionManager)
Output: List[EnrichedStory]

Processing order (Module 7.2 "local-first" doctrine):
  1. TagEnhancer on every raw event  — city → subdivision BEFORE dedup
  2. Deduplicate tagged events        — "IN-TN" stories cluster separately from "IN"
  3. Classify + extract geo entities
  4. Resolve coordinates via GeoResolver
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from ingestion_engine.core.models import NewsEvent
from intelligence_layer.classifier import classify
from intelligence_layer.deduplicator import deduplicate, DeduplicationResult
from intelligence_layer.entities import extract_mentioned_regions
from intelligence_layer.geo_resolver import GeoResolver
from intelligence_layer.geo_tagger import TagEnhancer
from intelligence_layer.models import EnrichedStory

logger = logging.getLogger(__name__)


class IntelligencePipeline:
    """
    Stateless processing pipeline.  Create once, call `process()` repeatedly.
    """

    def __init__(self) -> None:
        self._geo = GeoResolver()
        self._tagger = TagEnhancer()

    def process(self, events: List[NewsEvent]) -> List[EnrichedStory]:
        """
        Run the full intelligence pass over a list of raw NewsEvents.

        Steps:
          1. Tag every raw event with TagEnhancer (city → subdivision region_code).
          2. Deduplicate tagged events — local stories form distinct clusters.
          3. Classify the cluster lead's title + snippet.
          4. Extract geo-entities.
          5. Resolve coordinates via GeoResolver.
          6. Assemble EnrichedStory objects.
        """
        if not events:
            logger.info("IntelligencePipeline: No events to process.")
            return []

        logger.info("IntelligencePipeline: Processing %d events.", len(events))

        # ── Step 1: tag BEFORE dedup so city-resolved region codes drive clustering ──
        tagged: List[NewsEvent] = [self._tagger.enhance(e)[0] for e in events]
        tagged_count = sum(1 for t, o in zip(tagged, events) if t.region_code != o.region_code)
        if tagged_count:
            logger.info("IntelligencePipeline: TagEnhancer updated %d event(s).", tagged_count)

        # ── Step 2: deduplicate on the tagged list ─────────────────────────────────
        clusters: List[DeduplicationResult] = deduplicate(tagged)
        now = datetime.now(tz=timezone.utc)
        enriched: List[EnrichedStory] = []

        for cluster in clusters:
            lead = cluster.lead   # already has subdivision region_code if city was found
            category = classify(lead.title, lead.snippet)
            mentioned_regions = extract_mentioned_regions(
                lead.title, lead.snippet, lead.region_code
            )

            # ── Step 5: resolve coordinates ────────────────────────────────────────
            # region_code is already updated by TagEnhancer; no second pass needed.
            coords: Optional[Tuple[float, float]] = None
            rc = lead.region_code or ""

            if "-" in rc:
                country = rc.split("-")[0]
                coords = self._geo.get_coordinates(country, rc)
            else:
                coords = self._geo.get_coordinates(rc)

            lat = coords[0] if coords else None
            lng = coords[1] if coords else None

            enriched.append(
                EnrichedStory(
                    lead_event=lead,
                    secondary_sources=cluster.secondary_sources,
                    category=category,
                    mentioned_regions=mentioned_regions,
                    dedup_group_id=cluster.group_id,
                    processed_at=now,
                    latitude=lat,
                    longitude=lng,
                )
            )

        logger.info(
            "IntelligencePipeline: Produced %d enriched stories from %d raw events.",
            len(enriched),
            len(events),
        )
        return enriched
