from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from typing import List, Optional

import caldav
import recurring_ical_events
from icalendar import Calendar

from app.models import Event
from app.sources.base import CalendarSource
from app.sources.dt_utils import is_all_day, normalize_dt


class CalDAVSource(CalendarSource):
    """
    Calendar source backed by a live CalDAV server, e.g. Nextcloud's native
    calendar (no public ICS link needed — works with private calendars).

    url: the CalDAV principal/calendar URL, e.g.
         https://cloud.example.com/remote.php/dav/calendars/USERNAME/personal/
    username / password: Nextcloud credentials (use an app password, not
         your login password — generate one under Settings > Security).
    calendar_name: optional; if the url points at the calendar-home rather
         than a single calendar, filter to the calendar with this display name.
    """

    def __init__(
        self,
        name: str,
        url: str,
        username: str,
        password: str,
        calendar_name: Optional[str] = None,
    ):
        super().__init__(name)
        self.url = url
        self.username = username
        self.password = password
        self.calendar_name = calendar_name

    def _get_calendars_sync(self) -> List[caldav.Calendar]:
        client = caldav.DAVClient(url=self.url, username=self.username, password=self.password)
        principal = client.principal()
        calendars = principal.calendars()
        if self.calendar_name:
            calendars = [c for c in calendars if c.name == self.calendar_name]
        return calendars

    def _fetch_sync(self, day: date) -> List[Event]:
        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max)

        events: List[Event] = []
        for cal in self._get_calendars_sync():
            # Server-side time-range filtering — only fetches what's needed
            results = cal.search(start=start, end=end, event=True, expand=True)
            for caldav_obj in results:
                ical_text = caldav_obj.data
                vcal = Calendar.from_ical(ical_text)
                occurrences = recurring_ical_events.of(vcal).between(start, end)

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
                            location=str(component.get("LOCATION"))
                            if component.get("LOCATION")
                            else None,
                            source=self.name,
                            uid=str(component.get("UID")) if component.get("UID") else None,
                        )
                    )
        return events

    async def get_events_for_date(self, day: date) -> List[Event]:
        # caldav library is sync-only; run it in a thread so it doesn't block the event loop
        return await asyncio.to_thread(self._fetch_sync, day)
