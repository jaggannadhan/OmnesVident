import pytest
from datetime import datetime, timedelta, timezone
from ingestion_engine.core.models import NewsEvent
from intelligence_layer.deduplicator import (
    deduplicate,
    _normalize_url,
    _normalize_title,
    FUZZY_THRESHOLD,
)


def _event(
    title="Breaking News",
    url="https://example.com/article",
    region="US",
    hours_ago=0,
) -> NewsEvent:
    return NewsEvent(
        title=title,
        snippet="A test snippet.",
        source_url=url,
        source_name="TestSource",
        region_code=region,
        timestamp=datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago),
    )


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------

def test_normalize_url_strips_www():
    assert _normalize_url("https://www.bbc.co.uk/news/article") == \
           _normalize_url("https://bbc.co.uk/news/article")

def test_normalize_url_strips_trailing_slash():
    assert _normalize_url("https://example.com/page/") == \
           _normalize_url("https://example.com/page")

def test_normalize_url_strips_query_and_fragment():
    assert _normalize_url("https://example.com/page?utm_source=twitter#top") == \
           _normalize_url("https://example.com/page")


# ---------------------------------------------------------------------------
# Deduplication — exact URL
# ---------------------------------------------------------------------------

def test_exact_url_duplicates_merged():
    e1 = _event(title="Story A", url="https://example.com/story")
    e2 = _event(title="Story A copy", url="https://example.com/story")
    clusters = deduplicate([e1, e2])
    assert len(clusters) == 1
    assert len(clusters[0].secondary_sources) == 1


def test_www_url_treated_as_duplicate():
    e1 = _event(url="https://example.com/story")
    e2 = _event(url="https://www.example.com/story")
    clusters = deduplicate([e1, e2])
    assert len(clusters) == 1


# ---------------------------------------------------------------------------
# Deduplication — fuzzy title
# ---------------------------------------------------------------------------

def test_near_identical_titles_same_region_merged():
    e1 = _event(title="Apple unveils new iPhone model at event", url="https://a.com/1")
    e2 = _event(title="Apple unveils new iPhone model at its annual event", url="https://b.com/2")
    clusters = deduplicate([e1, e2])
    assert len(clusters) == 1


def test_similar_titles_different_region_not_merged():
    e1 = _event(title="President signs new trade bill", url="https://a.com/1", region="US")
    e2 = _event(title="President signs new trade bill", url="https://b.com/2", region="GB")
    clusters = deduplicate([e1, e2])
    assert len(clusters) == 2


def test_unrelated_titles_not_merged():
    e1 = _event(title="Stock markets hit record high", url="https://a.com/1")
    e2 = _event(title="Earthquake strikes coastal city", url="https://b.com/2")
    clusters = deduplicate([e1, e2])
    assert len(clusters) == 2


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

def test_similar_titles_outside_window_not_merged():
    e1 = _event(title="Big political vote today", url="https://a.com/1", hours_ago=25)
    e2 = _event(title="Big political vote today", url="https://b.com/2", hours_ago=0)
    clusters = deduplicate([e1, e2])
    assert len(clusters) == 2


def test_empty_input_returns_empty():
    assert deduplicate([]) == []


def test_single_event_returns_one_cluster():
    clusters = deduplicate([_event()])
    assert len(clusters) == 1
    assert clusters[0].secondary_sources == []


# ---------------------------------------------------------------------------
# Cluster lead selection (earliest timestamp becomes lead)
# ---------------------------------------------------------------------------

def test_earliest_event_is_lead():
    older = _event(title="Apple unveils iPhone 16 at annual keynote event", url="https://a.com/1", hours_ago=5)
    newer = _event(title="Apple unveils iPhone 16 at its annual keynote event", url="https://b.com/2", hours_ago=1)
    clusters = deduplicate([newer, older])  # intentionally reversed order
    assert len(clusters) == 1
    assert clusters[0].lead.source_url == older.source_url
