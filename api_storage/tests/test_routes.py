"""Tests for FastAPI endpoints using TestClient with in-memory DB."""

import json
from datetime import datetime, timezone

import pytest

from api_storage.database import StoryRecord
from sqlmodel import Session


def _seed_story(session: Session, **overrides) -> StoryRecord:
    defaults = dict(
        dedup_group_id="testaaaa",
        title="Test Headline",
        snippet="A snippet.",
        source_url="https://example.com/1",
        source_name="TestSource",
        region_code="US",
        timestamp=datetime.now(tz=timezone.utc),
        category="WORLD",
        mentioned_regions_json='["US"]',
        secondary_sources_json='[]',
        processed_at=datetime.now(tz=timezone.utc),
    )
    defaults.update(overrides)
    record = StoryRecord(**defaults)
    session.add(record)
    session.commit()
    return record


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# GET /news
# ---------------------------------------------------------------------------

def test_get_news_empty_db(client):
    resp = client.get("/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["stories"] == []


def test_get_news_returns_story(client, session):
    _seed_story(session)
    resp = client.get("/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["stories"][0]["title"] == "Test Headline"


def test_get_news_category_filter(client, session):
    _seed_story(session, dedup_group_id="pol00001", category="POLITICS")
    _seed_story(session, dedup_group_id="spo00001", category="SPORTS")
    resp = client.get("/news?category=POLITICS")
    assert resp.status_code == 200
    stories = resp.json()["stories"]
    assert len(stories) == 1
    assert stories[0]["category"] == "POLITICS"


def test_get_news_region_filter(client, session):
    _seed_story(session, dedup_group_id="us000001", region_code="US", mentioned_regions_json='["US"]')
    _seed_story(session, dedup_group_id="gb000001", region_code="GB", mentioned_regions_json='["GB"]')
    resp = client.get("/news?region=GB")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_news_pagination(client, session):
    for i in range(5):
        _seed_story(session, dedup_group_id=f"page000{i}", source_url=f"https://x.com/{i}")
    resp = client.get("/news?limit=2&offset=0")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["stories"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_get_news_story_shape(client, session):
    _seed_story(session)
    story = client.get("/news").json()["stories"][0]
    for field in ["dedup_group_id", "title", "snippet", "source_url",
                  "source_name", "region_code", "category",
                  "mentioned_regions", "secondary_sources",
                  "timestamp", "processed_at"]:
        assert field in story, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /news/{region_code}
# ---------------------------------------------------------------------------

def test_get_news_by_region(client, session):
    _seed_story(session, dedup_group_id="rg000001", region_code="JP",
                mentioned_regions_json='["JP"]')
    resp = client.get("/news/JP")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_news_by_region_cross_regional(client, session):
    """Story filed under GB but mentions FR should appear under /news/FR."""
    _seed_story(session, dedup_group_id="cr000001", region_code="GB",
                mentioned_regions_json='["GB", "FR"]')
    resp = client.get("/news/FR")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_news_by_region_invalid_code(client):
    resp = client.get("/news/INVALID")
    assert resp.status_code == 422


def test_get_news_by_region_empty_result(client):
    resp = client.get("/news/ZZ")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------

def _ingest_payload(n=2):
    return {
        "events": [
            {
                "title": f"Breaking news story number {i}",
                "snippet": "A snippet.",
                "source_url": f"https://example.com/{i}",
                "source_name": "TestSource",
                "region_code": "US",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
            for i in range(n)
        ]
    }


def test_ingest_returns_202(client):
    resp = client.post("/ingest", json=_ingest_payload(2))
    assert resp.status_code == 202


def test_ingest_response_schema(client):
    data = client.post("/ingest", json=_ingest_payload(3)).json()
    assert "accepted" in data
    assert "queued" in data
    assert "message" in data
    assert data["accepted"] == 3


def test_ingest_empty_events_rejected(client):
    resp = client.post("/ingest", json={"events": []})
    assert resp.status_code == 422


def test_ingest_missing_field_rejected(client):
    bad_payload = {"events": [{"title": "No URL here"}]}
    resp = client.post("/ingest", json=bad_payload)
    assert resp.status_code == 422
