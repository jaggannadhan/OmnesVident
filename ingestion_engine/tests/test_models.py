import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from ingestion_engine.core.models import NewsEvent


def _valid_event(**overrides) -> dict:
    base = {
        "title": "Test Headline",
        "snippet": "A short snippet.",
        "source_url": "https://example.com/article",
        "source_name": "Test Source",
        "region_code": "US",
        "timestamp": datetime.now(tz=timezone.utc),
    }
    base.update(overrides)
    return base


def test_valid_event_creation():
    event = NewsEvent(**_valid_event())
    assert event.title == "Test Headline"
    assert event.region_code == "US"


def test_missing_required_field_raises():
    data = _valid_event()
    del data["title"]
    with pytest.raises(ValidationError):
        NewsEvent(**data)


def test_serialises_to_json():
    event = NewsEvent(**_valid_event())
    payload = event.model_dump(mode="json")
    assert isinstance(payload["timestamp"], str)
    assert "title" in payload
