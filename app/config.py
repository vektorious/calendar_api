from __future__ import annotations

import os
from typing import List

import yaml

from app.sources.base import CalendarSource
from app.sources.caldav_source import CalDAVSource
from app.sources.ics_url import ICSUrlSource

CONFIG_PATH = os.environ.get("CALENDAR_CONFIG", "sources.yaml")

# Add new backend types here as you build them.
SOURCE_TYPES = {
    "ics_url": ICSUrlSource,
    "caldav": CalDAVSource,
}


def _resolve_env_vars(value):
    """Allow config values like '${NEXTCLOUD_PASSWORD}' to pull from the environment."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.environ.get(env_key, "")
    return value


def load_sources() -> List[CalendarSource]:
    if not os.path.exists(CONFIG_PATH):
        return []

    with open(CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f) or {}

    sources: List[CalendarSource] = []
    for entry in raw.get("sources", []):
        entry = dict(entry)  # copy
        source_type = entry.pop("type")
        cls = SOURCE_TYPES.get(source_type)
        if cls is None:
            raise ValueError(f"Unknown source type: {source_type!r}")

        # Resolve any ${ENV_VAR} placeholders (e.g. for passwords)
        kwargs = {k: _resolve_env_vars(v) for k, v in entry.items()}
        sources.append(cls(**kwargs))

    return sources
