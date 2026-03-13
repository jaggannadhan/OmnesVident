from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, field_serializer


class NewsEvent(BaseModel):
    title: str
    snippet: str
    source_url: str
    source_name: str
    region_code: str
    timestamp: datetime

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()
