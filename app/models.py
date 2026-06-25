from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Event(BaseModel):
    """A single calendar event, normalized across all sources."""

    name: str
    start: datetime
    end: Optional[datetime] = None
    all_day: bool = False
    location: Optional[str] = None
    source: str  # which configured source this came from
    uid: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}
