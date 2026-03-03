"""
Timezone utilities for local time display.

Converts UTC datetimes to local timezone for user-facing output.
Internal pipeline stays 100% UTC — conversion happens only at render time.

SPEC: docs/specs/bugfix/utc_localtime_display.md
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_tf_instance = None


def _get_tf():
    """Lazy singleton — TimezoneFinder loads ~12MB on first call."""
    global _tf_instance
    if _tf_instance is None:
        from timezonefinder import TimezoneFinder
        _tf_instance = TimezoneFinder()
    return _tf_instance


def tz_for_coords(lat: float, lon: float) -> ZoneInfo:
    """Coordinates → ZoneInfo. Falls back to UTC on error."""
    try:
        name = _get_tf().timezone_at(lat=lat, lng=lon)
        if name:
            return ZoneInfo(name)
    except Exception:
        pass
    return ZoneInfo("UTC")


def local_hour(dt: datetime, tz: ZoneInfo) -> int:
    """UTC datetime → local hour."""
    return dt.astimezone(tz).hour


def local_fmt(dt: datetime, tz: ZoneInfo, fmt: str = "%H:%M") -> str:
    """UTC datetime → formatted string in local timezone."""
    return dt.astimezone(tz).strftime(fmt)
