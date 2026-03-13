"""
IntelligencePipeline — chains deduplication → classification → geo-enrichment.

Input:  List[NewsEvent]   (raw output from IngestionManager)
Output: List[EnrichedStory]

The pipeline is synchronous because all three stages are CPU-bound / pure
Python.  Async wrappers can be added if this is called from an async context.
"""

import logging
from datetime import datetime, timezone
from typing import List

from ingestion_engine.core.models import NewsEvent
from intelligence_layer.classifier import classify
from intelligence_layer.deduplicator import deduplicate, DeduplicationResult
from intelligence_layer.entities import extract_mentioned_regions
from intelligence_layer.models import EnrichedStory

logger = logging.getLogger(__name__)


class IntelligencePipeline:
    """
    Stateless processing pipeline.  Create once, call `process()` repeatedly.
    """

    def process(self, events: List[NewsEvent]) -> List[EnrichedStory]:
        """
        Run the full intelligence pass over a list of raw NewsEvents.

        Steps:
          1. Deduplicate → produce DeduplicationResult clusters.
          2. Classify the lead event's title + snippet.
          3. Extract geo-entities from the lead event's title + snippet.
          4. Assemble EnrichedStory objects.
        """
        if not events:
            logger.info("IntelligencePipeline: No events to process.")
            return []

        logger.info("IntelligencePipeline: Processing %d events.", len(events))

        clusters: List[DeduplicationResult] = deduplicate(events)
        now = datetime.now(tz=timezone.utc)
        enriched: List[EnrichedStory] = []

        for cluster in clusters:
            lead = cluster.lead
            category = classify(lead.title, lead.snippet)
            mentioned_regions = extract_mentioned_regions(
                lead.title, lead.snippet, lead.region_code
            )

            enriched.append(
                EnrichedStory(
                    lead_event=lead,
                    secondary_sources=cluster.secondary_sources,
                    category=category,
                    mentioned_regions=mentioned_regions,
                    dedup_group_id=cluster.group_id,
                    processed_at=now,
                )
            )

        logger.info(
            "IntelligencePipeline: Produced %d enriched stories from %d raw events.",
            len(enriched),
            len(events),
        )
        return enriched
