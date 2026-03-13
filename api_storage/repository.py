"""
Repository layer: all database reads and writes go through here.

Public API:
  save_stories(session, stories)                  — upsert/merge batch
  get_latest_news(session, region, category, ...) — paginated query
  get_seen_group_ids(session, since_hours)         — stateful dedup check
  cleanup_old_seen_stories(session, older_than_hours) — maintenance
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set, Tuple

from sqlmodel import Session, col, select

from api_storage.database import SeenStory, StoryRecord
from intelligence_layer.models import EnrichedStory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def save_stories(session: Session, stories: List[EnrichedStory]) -> Tuple[int, int]:
    """
    Upsert a batch of EnrichedStory objects.

    For each story:
    - If `dedup_group_id` already exists in StoryRecord: merge the new
      secondary_sources into the existing row (avoid duplicate URLs).
    - Otherwise: insert a new StoryRecord row.

    Also upserts SeenStory for stateful cross-cycle deduplication.

    Returns (inserted_count, merged_count).
    """
    inserted = 0
    merged = 0
    now = datetime.now(tz=timezone.utc)

    for story in stories:
        existing: Optional[StoryRecord] = session.exec(
            select(StoryRecord).where(
                StoryRecord.dedup_group_id == story.dedup_group_id
            )
        ).first()

        if existing:
            # Merge secondary sources, avoiding duplicates
            current_sources: List[str] = existing.secondary_sources
            new_sources = [
                url for url in story.secondary_sources
                if url not in current_sources
            ]
            if new_sources:
                existing.secondary_sources = current_sources + new_sources
                session.add(existing)
            merged += 1
            logger.debug("Merged story: %s", story.dedup_group_id)
        else:
            record = StoryRecord(
                dedup_group_id=story.dedup_group_id,
                title=story.lead_event.title,
                snippet=story.lead_event.snippet,
                source_url=story.lead_event.source_url,
                source_name=story.lead_event.source_name,
                region_code=story.lead_event.region_code,
                timestamp=story.lead_event.timestamp,
                category=story.category,
                mentioned_regions_json=json.dumps(story.mentioned_regions),
                secondary_sources_json=json.dumps(story.secondary_sources),
                processed_at=story.processed_at,
            )
            session.add(record)
            inserted += 1
            logger.debug("Inserted story: %s", story.dedup_group_id)

        # Upsert SeenStory
        seen: Optional[SeenStory] = session.get(SeenStory, story.dedup_group_id)
        if seen:
            seen.last_seen_at = now
            session.add(seen)
        else:
            session.add(
                SeenStory(
                    dedup_group_id=story.dedup_group_id,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )

    session.commit()
    logger.info("save_stories: inserted=%d, merged=%d", inserted, merged)
    return inserted, merged


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_latest_news(
    session: Session,
    region: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[StoryRecord], int]:
    """
    Return (stories, total_count) ordered by timestamp descending.

    Region filter matches:
      - The primary region_code column (exact match), OR
      - The mentioned_regions_json column (JSON array contains the code).

    This dual-match enables cross-regional story discovery: a UK story
    about Japan is returned when filtering by both GB and JP.
    """
    query = select(StoryRecord)

    if category:
        query = query.where(StoryRecord.category == category.upper())

    if region:
        region_upper = region.upper()
        query = query.where(
            (StoryRecord.region_code == region_upper)
            | StoryRecord.mentioned_regions_json.contains(f'"{region_upper}"')
        )

    query = query.order_by(col(StoryRecord.timestamp).desc())

    total = len(session.exec(query).all())
    stories = session.exec(query.offset(offset).limit(limit)).all()

    return list(stories), total


def get_seen_group_ids(session: Session, since_hours: int = 24) -> Set[str]:
    """
    Return all dedup_group_ids seen within the last `since_hours` hours.

    Used by the ingest route to skip stories the Intelligence Layer would
    re-produce for events already in the database.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=since_hours)
    results = session.exec(
        select(SeenStory).where(SeenStory.last_seen_at >= cutoff)
    ).all()
    return {row.dedup_group_id for row in results}


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def cleanup_old_seen_stories(session: Session, older_than_hours: int = 48) -> int:
    """
    Delete SeenStory rows older than `older_than_hours`.

    Called on app startup and opportunistically during ingest to keep the
    table lean.  Returns the number of rows deleted.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=older_than_hours)
    rows = session.exec(
        select(SeenStory).where(SeenStory.last_seen_at < cutoff)
    ).all()
    for row in rows:
        session.delete(row)
    session.commit()
    if rows:
        logger.info("cleanup_old_seen_stories: removed %d stale entries.", len(rows))
    return len(rows)
