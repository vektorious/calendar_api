from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional


def normalize_dt(value, is_all_day_anchor: bool = False) -> datetime:
    """
    Normalize an icalendar DTSTART/DTEND value (which may be a date,
    a naive datetime, or a tz-aware datetime) into a consistent,
    timezone-aware datetime so that events from different sources
    (and different timezones) can be safely sorted and compared.

    Date-only values (all-day events) become midnight UTC.
    Naive datetimes are assumed to already represent local wall-clock
    time and are tagged as UTC (icalendar normally gives us tz-aware
    values for anything with a real timezone; naive values are rare
    and usually floating-time events).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    # plain date (all-day event)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def is_all_day(value) -> bool:
    return not isinstance(value, datetime)
