"""Tests for repository CRUD, upsert/merge, and maintenance logic."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from api_storage.database import SeenStory, StoryRecord
from api_storage.repository import (
    cleanup_old_seen_stories,
    get_latest_news,
    get_seen_group_ids,
    save_stories,
)
from intelligence_layer.models import EnrichedStory
from ingestion_engine.core.models import NewsEvent


def _news_event(title="Headline", url="https://example.com/1", region="US") -> NewsEvent:
    return NewsEvent(
        title=title,
        snippet="Snippet.",
        source_url=url,
        source_name="TestSource",
        region_code=region,
        timestamp=datetime.now(tz=timezone.utc),
    )


def _story(
    title="Headline",
    url="https://example.com/1",
    region="US",
    category="WORLD",
    group_id="abc12345",
    secondary_sources=None,
    mentioned_regions=None,
) -> EnrichedStory:
    return EnrichedStory(
        lead_event=_news_event(title, url, region),
        secondary_sources=secondary_sources or [],
        category=category,
        mentioned_regions=mentioned_regions or [region],
        dedup_group_id=group_id,
        processed_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# save_stories — insert
# ---------------------------------------------------------------------------

def test_save_new_story_inserts_row(session):
    inserted, merged = save_stories(session, [_story()])
    assert inserted == 1
    assert merged == 0
    assert session.get(StoryRecord, 1) is not None


def test_save_populates_all_fields(session):
    save_stories(session, [_story(title="Test Title", region="GB", category="POLITICS")])
    record = session.exec(
        __import__("sqlmodel").select(StoryRecord)
    ).first()
    assert record.title == "Test Title"
    assert record.region_code == "GB"
    assert record.category == "POLITICS"


def test_save_creates_seen_story_entry(session):
    save_stories(session, [_story(group_id="deadbeef")])
    seen = session.get(SeenStory, "deadbeef")
    assert seen is not None


# ---------------------------------------------------------------------------
# save_stories — upsert/merge
# ---------------------------------------------------------------------------

def test_duplicate_group_id_merges_not_inserts(session):
    s1 = _story(group_id="aabb1122", url="https://a.com/1")
    s2 = _story(group_id="aabb1122", url="https://b.com/2", secondary_sources=["https://b.com/2"])

    inserted1, merged1 = save_stories(session, [s1])
    inserted2, merged2 = save_stories(session, [s2])

    assert inserted1 == 1
    assert merged2 == 1

    from sqlmodel import select
    records = session.exec(select(StoryRecord)).all()
    assert len(records) == 1  # No duplicate row


def test_merge_appends_secondary_sources(session):
    s1 = _story(group_id="cc334455", url="https://a.com/1")
    s2 = _story(group_id="cc334455", url="https://a.com/1", secondary_sources=["https://b.com/2"])

    save_stories(session, [s1])
    save_stories(session, [s2])

    from sqlmodel import select
    record = session.exec(select(StoryRecord)).first()
    assert "https://b.com/2" in record.secondary_sources


def test_merge_does_not_duplicate_existing_sources(session):
    s1 = _story(group_id="ee556677", url="https://a.com/1", secondary_sources=["https://b.com/2"])
    save_stories(session, [s1])
    save_stories(session, [s1])  # Same sources again

    from sqlmodel import select
    record = session.exec(select(StoryRecord)).first()
    assert record.secondary_sources.count("https://b.com/2") == 1


# ---------------------------------------------------------------------------
# get_latest_news
# ---------------------------------------------------------------------------

def test_get_latest_news_returns_all(session):
    save_stories(session, [
        _story(title="A", url="https://a.com", group_id="00000001"),
        _story(title="B", url="https://b.com", group_id="00000002"),
    ])
    stories, total = get_latest_news(session)
    assert total == 2
    assert len(stories) == 2


def test_get_latest_news_filters_by_category(session):
    save_stories(session, [
        _story(title="Politics", url="https://a.com", group_id="10000001", category="POLITICS"),
        _story(title="Sports", url="https://b.com", group_id="10000002", category="SPORTS"),
    ])
    stories, total = get_latest_news(session, category="POLITICS")
    assert total == 1
    assert stories[0].category == "POLITICS"


def test_get_latest_news_filters_by_primary_region(session):
    save_stories(session, [
        _story(url="https://a.com", group_id="20000001", region="US"),
        _story(url="https://b.com", group_id="20000002", region="GB"),
    ])
    stories, total = get_latest_news(session, region="US")
    assert total == 1
    assert stories[0].region_code == "US"


def test_get_latest_news_cross_regional_discovery(session):
    """A GB story mentioning JP should appear in JP filter results."""
    s = _story(
        url="https://a.com", group_id="30000001",
        region="GB", mentioned_regions=["GB", "JP"],
    )
    save_stories(session, [s])
    stories, total = get_latest_news(session, region="JP")
    assert total == 1


def test_get_latest_news_pagination(session):
    stories_to_save = [
        _story(url=f"https://x.com/{i}", group_id=f"4000000{i}") for i in range(5)
    ]
    save_stories(session, stories_to_save)
    page1, total = get_latest_news(session, limit=2, offset=0)
    page2, _ = get_latest_news(session, limit=2, offset=2)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2


def test_get_latest_news_ordered_by_timestamp_desc(session):
    older = EnrichedStory(
        lead_event=NewsEvent(
            title="Old", snippet="s", source_url="https://old.com",
            source_name="S", region_code="US",
            timestamp=datetime.now(tz=timezone.utc) - timedelta(hours=5),
        ),
        category="WORLD", mentioned_regions=["US"],
        dedup_group_id="older000", processed_at=datetime.now(tz=timezone.utc),
    )
    newer = EnrichedStory(
        lead_event=NewsEvent(
            title="New", snippet="s", source_url="https://new.com",
            source_name="S", region_code="US",
            timestamp=datetime.now(tz=timezone.utc),
        ),
        category="WORLD", mentioned_regions=["US"],
        dedup_group_id="newer000", processed_at=datetime.now(tz=timezone.utc),
    )
    save_stories(session, [older, newer])
    stories, _ = get_latest_news(session)
    assert stories[0].dedup_group_id == "newer000"


# ---------------------------------------------------------------------------
# Stateful dedup — get_seen_group_ids
# ---------------------------------------------------------------------------

def test_seen_group_ids_within_window(session):
    save_stories(session, [_story(group_id="seenaaaa")])
    ids = get_seen_group_ids(session, since_hours=24)
    assert "seenaaaa" in ids


def test_seen_group_ids_outside_window_excluded(session):
    # Insert a SeenStory with an old timestamp
    old_seen = SeenStory(
        dedup_group_id="oldstory",
        first_seen_at=datetime.now(tz=timezone.utc) - timedelta(hours=30),
        last_seen_at=datetime.now(tz=timezone.utc) - timedelta(hours=30),
    )
    session.add(old_seen)
    session.commit()
    ids = get_seen_group_ids(session, since_hours=24)
    assert "oldstory" not in ids


# ---------------------------------------------------------------------------
# Maintenance — cleanup_old_seen_stories
# ---------------------------------------------------------------------------

def test_cleanup_removes_old_entries(session):
    old = SeenStory(
        dedup_group_id="stale001",
        first_seen_at=datetime.now(tz=timezone.utc) - timedelta(hours=60),
        last_seen_at=datetime.now(tz=timezone.utc) - timedelta(hours=60),
    )
    fresh = SeenStory(
        dedup_group_id="fresh001",
        first_seen_at=datetime.now(tz=timezone.utc),
        last_seen_at=datetime.now(tz=timezone.utc),
    )
    session.add(old)
    session.add(fresh)
    session.commit()

    removed = cleanup_old_seen_stories(session, older_than_hours=48)
    assert removed == 1
    assert session.get(SeenStory, "stale001") is None
    assert session.get(SeenStory, "fresh001") is not None


def test_cleanup_returns_zero_when_nothing_to_clean(session):
    assert cleanup_old_seen_stories(session, older_than_hours=48) == 0
