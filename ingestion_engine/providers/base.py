from abc import ABC, abstractmethod
from typing import List

from ingestion_engine.core.models import NewsEvent


class BaseProvider(ABC):
    """Abstract base class for all news providers."""

    @abstractmethod
    async def fetch(self) -> List[NewsEvent]:
        """Fetch news events from the provider source."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging/debugging."""
        ...
