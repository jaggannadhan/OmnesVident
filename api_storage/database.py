"""
Database engine, ORM table definitions, and session management.

Two tables:
  StoryRecord  — persisted EnrichedStory (lead event flattened + JSON arrays).
  SeenStory    — lightweight cross-cycle dedup state table.

SQLite is used for the MVP.  Switching to PostgreSQL requires only changing
DATABASE_URL and removing the check_same_thread argument.
"""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, List, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./omnesvident.db")

# check_same_thread=False is required for SQLite when the same connection is
# accessed from multiple threads (e.g. FastAPI test client).
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


# ---------------------------------------------------------------------------
# ORM table models
# ---------------------------------------------------------------------------

class StoryRecord(SQLModel, table=True):
    """
    Flattened representation of an EnrichedStory suitable for SQL storage.

    Array fields (mentioned_regions, secondary_sources) are stored as JSON
    strings.  Helpers on this class handle (de)serialization.
    """

    __tablename__ = "story_record"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Dedup identity
    dedup_group_id: str = Field(index=True, unique=True, max_length=8)

    # Lead event fields (flattened for queryability)
    title: str
    snippet: str
    source_url: str
    source_name: str
    region_code: str = Field(index=True, max_length=2)
    timestamp: datetime

    # Intelligence layer enrichments
    category: str = Field(index=True)
    mentioned_regions_json: str = Field(default="[]")   # JSON: List[str]
    secondary_sources_json: str = Field(default="[]")   # JSON: List[str]
    processed_at: datetime

    # Geo-Intelligence (Module 6)
    latitude: Optional[float] = Field(default=None)     # WGS84 decimal degrees
    longitude: Optional[float] = Field(default=None)    # WGS84 decimal degrees

    # ---------------------
    @property
    def mentioned_regions(self) -> List[str]:
        return json.loads(self.mentioned_regions_json)

    @mentioned_regions.setter
    def mentioned_regions(self, value: List[str]) -> None:
        self.mentioned_regions_json = json.dumps(value)

    @property
    def secondary_sources(self) -> List[str]:
        return json.loads(self.secondary_sources_json)

    @secondary_sources.setter
    def secondary_sources(self, value: List[str]) -> None:
        self.secondary_sources_json = json.dumps(value)


class SeenStory(SQLModel, table=True):
    """
    Cross-cycle deduplication state.  One row per dedup_group_id.

    Rows older than 48 hours are purged by cleanup_old_seen_stories() to
    keep this table lightweight.
    """

    __tablename__ = "seen_story"

    dedup_group_id: str = Field(primary_key=True, max_length=8)
    first_seen_at: datetime
    last_seen_at: datetime


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# FastAPI-compatible dependency (yields, no context manager)
def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
