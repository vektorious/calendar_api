from __future__ import annotations

import logging
import os
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("calendar-api")


def _load_display_tz() -> ZoneInfo | timezone:
    """
    Timezone all event datetimes are presented in, from the DISPLAY_TZ env var
    (an IANA name like 'Europe/Berlin'). Defaults to UTC. Resolved via the
    `tzdata` package, so it works on slim images without system zoneinfo.
    """
    name = os.environ.get("DISPLAY_TZ", "UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Invalid DISPLAY_TZ %r, falling back to UTC", name)
        return timezone.utc


DISPLAY_TZ = _load_display_tz()


def normalize_dt(value) -> datetime:
    """
    Normalize an icalendar DTSTART/DTEND value (which may be a date,
    a naive datetime, or a tz-aware datetime) into a timezone-aware datetime
    expressed in DISPLAY_TZ, so events from different sources and timezones
    sort together correctly AND display in one consistent timezone.

    Date-only values (all-day events) are anchored at midnight in DISPLAY_TZ
    so the calendar day is preserved (their time of day isn't shown anyway).
    Naive datetimes are assumed to be UTC (icalendar normally gives tz-aware
    values for anything with a real timezone; naive values are rare floating
    times) and then converted to DISPLAY_TZ.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(DISPLAY_TZ)
    # plain date (all-day event) -> midnight in the display timezone
    return datetime.combine(value, time.min, tzinfo=DISPLAY_TZ)


def is_all_day(value) -> bool:
    return not isinstance(value, datetime)
