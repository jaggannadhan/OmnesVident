import pytest
from datetime import datetime, timezone
from ingestion_engine.core.models import NewsEvent
from intelligence_layer.pipeline import IntelligencePipeline
from intelligence_layer.models import EnrichedStory
from intelligence_layer.classifier import CATEGORIES


def _event(title="Headline", url="https://example.com/1", region="US") -> NewsEvent:
    return NewsEvent(
        title=title,
        snippet="A snippet for testing.",
        source_url=url,
        source_name="TestSource",
        region_code=region,
        timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def pipeline():
    return IntelligencePipeline()


def test_empty_input_returns_empty(pipeline):
    assert pipeline.process([]) == []


def test_returns_enriched_story_instances(pipeline):
    results = pipeline.process([_event()])
    assert len(results) == 1
    assert isinstance(results[0], EnrichedStory)


def test_enriched_story_has_valid_category(pipeline):
    results = pipeline.process([_event("World Cup final match today")])
    assert results[0].category in CATEGORIES


def test_enriched_story_contains_lead_event(pipeline):
    event = _event("Test headline", url="https://example.com/test")
    results = pipeline.process([event])
    assert results[0].lead_event.source_url == event.source_url


def test_deduplicated_events_produce_single_story(pipeline):
    e1 = _event("Apple unveils new iPhone model", url="https://a.com/1")
    e2 = _event("Apple unveils new iPhone model today", url="https://b.com/2")
    results = pipeline.process([e1, e2])
    assert len(results) == 1
    assert len(results[0].secondary_sources) == 1


def test_distinct_events_produce_multiple_stories(pipeline):
    e1 = _event("Stock market crashes", url="https://a.com/1")
    e2 = _event("Earthquake hits Pacific coast", url="https://b.com/2")
    results = pipeline.process([e1, e2])
    assert len(results) == 2


def test_mentioned_regions_includes_primary(pipeline):
    event = _event("Local news update", url="https://au.com/1", region="AU")
    results = pipeline.process([event])
    assert "AU" in results[0].mentioned_regions


def test_dedup_group_id_is_8_chars(pipeline):
    results = pipeline.process([_event()])
    assert len(results[0].dedup_group_id) == 8


def test_processed_at_is_utc(pipeline):
    results = pipeline.process([_event()])
    assert results[0].processed_at.tzinfo is not None
