from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import List

from app.models import Event


class CalendarSource(ABC):
    """
    Interface every calendar backend must implement.

    Add a new backend (Google Calendar, Outlook, a local .ics file, etc.)
    by subclassing this and implementing get_events_for_date().
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def get_events_for_date(self, day: date) -> List[Event]:
        """Return all events that occur on the given calendar day (local time)."""
        raise NotImplementedError
