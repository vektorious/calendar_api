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
    max_events: int = Query(8, ge=1, le=50, description="Cap on total events returned, so the display never overflows."),
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

    # Fetch every day in the window concurrently, then group.
    per_day = await asyncio.gather(
        *(_gather_events(today + timedelta(days=offset)) for offset in range(days))
    )

    day_groups = []
    remaining = max_events
    for offset, events in enumerate(per_day):
        if remaining <= 0:
            break
        if not events:
            continue
        d = today + timedelta(days=offset)
        trimmed = events[:remaining]
        remaining -= len(trimmed)
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
                for e in trimmed
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
