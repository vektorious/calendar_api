from __future__ import annotations

from datetime import date, datetime, time
from typing import List

import httpx
import recurring_ical_events
from icalendar import Calendar

from app.models import Event
from app.sources.base import CalendarSource
from app.sources.dt_utils import is_all_day, normalize_dt


class ICSUrlSource(CalendarSource):
    """
    Calendar source backed by a remote .ics URL (e.g. a public Google Calendar
    export link, a Nextcloud calendar's public share link ending in
    "?export", or any other standard iCalendar feed).
    """

    def __init__(self, name: str, url: str, timeout: float = 10.0):
        super().__init__(name)
        self.url = url
        self.timeout = timeout

    async def _fetch_ics_text(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
            return resp.text

    async def get_events_for_date(self, day: date) -> List[Event]:
        ics_text = await self._fetch_ics_text()
        cal = Calendar.from_ical(ics_text)

        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max)

        # recurring_ical_events expands RRULEs and clips to the window for us
        occurrences = recurring_ical_events.of(cal).between(start, end)

        events: List[Event] = []
        for component in occurrences:
            dtstart = component.get("DTSTART").dt
            dtend_prop = component.get("DTEND")
            dtend = dtend_prop.dt if dtend_prop else None

            events.append(
                Event(
                    name=str(component.get("SUMMARY", "(no title)")),
                    start=normalize_dt(dtstart),
                    end=normalize_dt(dtend) if dtend is not None else None,
                    all_day=is_all_day(dtstart),
                    location=str(component.get("LOCATION")) if component.get("LOCATION") else None,
                    source=self.name,
                    uid=str(component.get("UID")) if component.get("UID") else None,
                )
            )

        return events
