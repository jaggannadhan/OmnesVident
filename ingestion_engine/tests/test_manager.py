import asyncio
import pytest
from datetime import datetime, timezone
from typing import List

from ingestion_engine.core.models import NewsEvent
from ingestion_engine.core.manager import IngestionManager
from ingestion_engine.providers.base import BaseProvider


def _make_event(title: str = "Headline") -> NewsEvent:
    return NewsEvent(
        title=title,
        snippet="Snippet.",
        source_url="https://example.com",
        source_name="Test",
        region_code="US",
        timestamp=datetime.now(tz=timezone.utc),
    )


class GoodProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "GoodProvider"

    async def fetch(self) -> List[NewsEvent]:
        return [_make_event("From Good"), _make_event("Also From Good")]


class BrokenProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "BrokenProvider"

    async def fetch(self) -> List[NewsEvent]:
        raise RuntimeError("Simulated failure")


@pytest.mark.asyncio
async def test_manager_collects_all_events():
    manager = IngestionManager(providers=[GoodProvider(), GoodProvider()])
    events = await manager.run()
    assert len(events) == 4


@pytest.mark.asyncio
async def test_manager_isolates_broken_provider():
    manager = IngestionManager(providers=[GoodProvider(), BrokenProvider()])
    events = await manager.run()
    # BrokenProvider returns nothing; GoodProvider's 2 events still returned
    assert len(events) == 2


@pytest.mark.asyncio
async def test_manager_empty_providers():
    manager = IngestionManager(providers=[])
    events = await manager.run()
    assert events == []
