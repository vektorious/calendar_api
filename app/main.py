from __future__ import annotations

import asyncio
import calendar as _calendar
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from app.auth import require_api_key
from app.config import load_sources
from app.models import Event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calendar-api")

app = FastAPI(title="Calendar Aggregator API", version="0.1.0")

# Loaded once at startup. Restart the service (or hit a future /reload route)
# after editing sources.yaml.
sources = load_sources()


async def _gather_events(day: date) -> List[Event]:
    async def safe_fetch(source):
        try:
            return await source.get_events_for_date(day)
        except Exception as exc:
            # One broken calendar source shouldn't take down the whole response.
            logger.warning("Source %r failed: %s", source.name, exc)
            return []

    results = await asyncio.gather(*(safe_fetch(s) for s in sources))
    all_events = [event for sublist in results for event in sublist]
    all_events.sort(key=lambda e: e.start)
    return all_events


@app.get("/today", response_model=List[Event])
async def get_today(_: str = Depends(require_api_key)):
    """All events occurring today, across all configured calendar sources."""
    if not sources:
        raise HTTPException(status_code=503, detail="No calendar sources configured (see sources.yaml)")
    return await _gather_events(date.today())


@app.get("/events", response_model=List[Event])
async def get_events(
    on: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) to fetch events for. Defaults to today."),
    _: str = Depends(require_api_key),
):
    """Same as /today but for an arbitrary date, e.g. /events?on=2026-07-04"""
    if not sources:
        raise HTTPException(status_code=503, detail="No calendar sources configured (see sources.yaml)")

    target_day = date.today()
    if on:
        try:
            target_day = datetime.strptime(on, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="`on` must be in YYYY-MM-DD format")

    return await _gather_events(target_day)


# Locale-independent English labels (the container's locale is unspecified, so
# we don't rely on strftime("%A") which would follow LC_TIME).
_WEEKDAY_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_LONG = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
_CAL_HEADERS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]  # week starts Monday


@app.get("/upcoming")
async def get_upcoming(
    days: int = Query(7, ge=1, le=31, description="How many days ahead to include (starting today)."),
    max_events: int = Query(6, ge=1, le=50, description="Row budget: each event AND each date-only gap day counts as one row, so the display never overflows."),
    _: str = Depends(require_api_key),
):
    """
    Day-grouped agenda for an e-ink display: today's date, a month grid (for a
    mini calendar), and upcoming events grouped by day. Days with no events are
    omitted, and events are capped at `max_events` total so the rendered screen
    has a clean bottom edge ("tune by count").
    """
    if not sources:
        raise HTTPException(status_code=503, detail="No calendar sources configured (see sources.yaml)")

    today = date.today()

    # Fetch every day in the window concurrently.
    per_day = await asyncio.gather(
        *(_gather_events(today + timedelta(days=offset)) for offset in range(days))
    )

    # Cap how much we show so the display has a clean bottom edge. Each shown
    # event AND each date-only gap day counts as one "row" against max_events.
    # Gaps between event days are filled (date-only); trailing empty days after
    # the last event are not padded on.
    shown = []          # ordered list of (day offset, events to show)
    used = 0
    pending_empty = []  # gap days held until a following event day commits them
    for offset, events in enumerate(per_day):
        if used >= max_events:
            break
        if not events:
            pending_empty.append(offset)
            continue
        # Need room for the intervening gap days plus at least one event.
        if used + len(pending_empty) >= max_events:
            break
        for empty_offset in pending_empty:
            shown.append((empty_offset, []))
            used += 1
        pending_empty = []
        take = events[: max_events - used]
        used += len(take)
        shown.append((offset, take))

    # If nothing is upcoming at all, still show today as a date-only row.
    if not shown:
        shown = [(0, [])]

    day_groups = []
    for offset, events in shown:
        d = today + timedelta(days=offset)
        day_groups.append({
            "day": d.day,
            "weekday_short": _WEEKDAY_SHORT[d.weekday()],
            "events": [
                {
                    "name": e.name,
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat() if e.end else None,
                    "all_day": e.all_day,
                    "source": e.source,
                }
                for e in events
            ],
        })

    # Month grid for the mini calendar (Monday-first; 0 marks padding cells).
    weeks = _calendar.Calendar(firstweekday=0).monthdayscalendar(today.year, today.month)

    return {
        "today": {
            "day": today.day,
            "weekday_long": _WEEKDAY_LONG[today.weekday()],
            "month_long": _MONTH_LONG[today.month],
            "year": today.year,
        },
        "calendar": {
            "weekday_headers": _CAL_HEADERS,
            "weeks": weeks,
            "today": today.day,
        },
        "days": day_groups,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "sources_configured": [s.name for s in sources]}
