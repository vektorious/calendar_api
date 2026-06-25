from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
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


@app.get("/health")
async def health():
    return {"status": "ok", "sources_configured": [s.name for s in sources]}
