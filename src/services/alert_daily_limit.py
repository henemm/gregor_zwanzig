"""Alert-Tages-Obergrenze nach Nutzerlevel (Issue #1070, Epic #1067 Slice 3).

SPEC: docs/specs/modules/alert_daily_limit.md

Persistiert einen pro-Nutzer-Tageszähler proaktiver Alerts (Deviation +
Radar/Onset) unter ``data/users/<user_id>/alert_daily_count.json``. Reset
erfolgt bei Kalendertag-Wechsel in Europe/Vienna (nicht UTC). ``now`` ist
durchgehend Funktionsparameter — kein ``datetime.now()`` in diesem Modul.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.user_tier import daily_alert_limit

VIENNA = ZoneInfo("Europe/Vienna")


def _counter_path(user_id: str) -> Path:
    return Path(f"data/users/{user_id}/alert_daily_count.json")


def _vienna_date_str(now: datetime) -> str:
    return now.astimezone(VIENNA).date().isoformat()


def load(user_id: str, now: datetime) -> int:
    """Return the current alert count for the Vienna-calendar-day of `now`.

    Pure read: if the stored date does not match today's Vienna date, this
    returns 0 WITHOUT writing anything (reset is load-only semantics).
    """
    path = _counter_path(user_id)
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    if data.get("date") != _vienna_date_str(now):
        return 0
    return int(data.get("count", 0))


def is_allowed(user_id: str, now: datetime) -> bool:
    """Return True if another alert may be sent today for this user."""
    limit = daily_alert_limit(user_id)
    if limit is None:
        return True
    return load(user_id, now) < limit


def increment(user_id: str, now: datetime) -> None:
    """Read-modify-write the daily counter, resetting on a new Vienna day."""
    path = _counter_path(user_id)
    today = _vienna_date_str(now)
    count = 0
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if data.get("date") == today:
                count = int(data.get("count", 0))
        except (json.JSONDecodeError, OSError):
            count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": today, "count": count + 1}))
