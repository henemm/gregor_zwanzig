"""Alert-Tages-Obergrenze nach Nutzerlevel (Issue #1070, Epic #1067 Slice 3).

SPEC: docs/specs/modules/alert_daily_limit.md

Persistiert einen pro-Nutzer-Tageszähler proaktiver Alerts (Deviation +
Radar/Onset + Compare, Issue #1213) unter
``<get_data_dir(user_id)>/alert_daily_count.json`` (respektiert
`GZ_DATA_DIR`/`_DATA_ROOT`, #1133). Reset erfolgt bei Kalendertag-Wechsel in
der ORTSZONE des Gegenstands (Issue #1726) — ein Zaehler JE ZONE:
``{"zones": {"Europe/Vienna": {"date": "2026-08-12", "count": 2}, ...}}``.
Bewusster Preis: wer Objekte in drei Zonen hat, bekommt das Kontingent
dreimal. Die Alternative (EIN Datensatz, jeder Aufrufer bringt seine Zone mit)
schriebe ``date`` zwischen zwei Kalendertagen hin und her — ``increment()``
setzt bei Nichttreffer auf 1 zurueck, das Limit griffe NIE.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.user_tier import daily_alert_limit
from utils.timezone import local_dt

#: Zone, unter der ein Zaehler im ALTEN Schema (Top-Level ``date``/``count``)
#: uebernommen wird: der Altbestand wurde de facto nach Wiener Kalendertag
#: gefuehrt. Jede andere Zone beginnt bei 0 — grosszuegiger, nie enger.
_LEGACY_ZONE_KEY = "Europe/Vienna"


def _counter_path(user_id: str) -> Path:
    from app.loader import get_data_dir
    return get_data_dir(user_id) / "alert_daily_count.json"


def _local_date_str(now: datetime, zone: ZoneInfo) -> str:
    return local_dt(now, zone).date().isoformat()


def _load_zones(path: Path) -> dict:
    """Alle Zonen-Zaehler der Datei, Alt-Schema eingeschlossen. Grundlage des
    Merge auf ZONEN-Ebene (Projektregel): der Aufrufer bekommt IMMER den ganzen
    Bestand und schreibt nur seinen Schluessel neu. Die Migration ist idempotent
    und geschieht beim naechsten Zugriff."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    zones = data.get("zones")
    if isinstance(zones, dict):
        return zones
    if data.get("date"):
        return {_LEGACY_ZONE_KEY: {"date": data["date"], "count": data.get("count", 0)}}
    return {}


def _count_for(zones: dict, zone: ZoneInfo, today: str) -> int:
    entry = zones.get(str(zone))
    if not isinstance(entry, dict) or entry.get("date") != today:
        return 0
    try:
        return int(entry.get("count", 0))
    except (TypeError, ValueError):
        return 0


def load(user_id: str, now: datetime, zone: ZoneInfo) -> int:
    """Zaehlerstand fuer den Kalendertag von `now` IN `zone`. Pure read: passt
    der gespeicherte Tag nicht zum Ortstag, liefert die Funktion 0, OHNE etwas
    zu schreiben. `zone` ist PFLICHT — ein Default waere ein stiller Rueckfall
    auf eine geratene Zone, also genau der behobene Fehler."""
    return _count_for(
        _load_zones(_counter_path(user_id)), zone, _local_date_str(now, zone)
    )


# Issue #1555: feste Reserve-Tabelle je endlichem `limit`-Wert. Reserviert
# einen Mindestanteil des geteilten Tagesbudgets ausschließlich für
# `reason="nowcast"` -- `reason="forecast_change"` prüft gegen `limit -
# RESERVE` statt gegen das volle `limit`. Nur `2`/`4` sind heute über
# `user_tier.daily_alert_limit` erreichbar (s. Spec "Known Limitations").
_FORECAST_CHANGE_RESERVE = {2: 1, 4: 2}


def is_allowed(
    user_id: str, now: datetime, zone: ZoneInfo, reason: str | None = None
) -> bool:
    """Return True if another alert may be sent today for this user IN `zone`.

    `reason="forecast_change"` prüft bei endlichem `limit` gegen eine um die
    NowCast-Reserve reduzierte Obergrenze (#1555). Jeder andere `reason`
    (inkl. `None`) prüft unverändert gegen das volle `limit`.
    """
    limit = daily_alert_limit(user_id)
    if limit is None:
        return True
    effective_limit = limit
    if reason == "forecast_change":
        effective_limit = limit - _FORECAST_CHANGE_RESERVE.get(limit, 0)
    return load(user_id, now, zone) < effective_limit


def increment(user_id: str, now: datetime, zone: ZoneInfo) -> None:
    """Read-modify-write des Zaehlers DIESER Zone, Reset am dortigen Ortstag.

    Issue #1213: atomarer Write (tmp-Datei + `os.replace`) statt direktem
    `write_text` — verhindert einen halb geschriebenen/korrupten Zähler bei
    gleichzeitigem Zugriff (Scheduler + API). Issue #1726: geschrieben wird der
    GESAMTE Zonen-Bestand zurueck, nur mit dem eigenen Schluessel erhoeht —
    Merge auf Zonen-Ebene, nicht bloss auf Datei-Ebene.
    """
    path = _counter_path(user_id)
    today = _local_date_str(now, zone)
    zones = _load_zones(path)
    zones[str(zone)] = {"date": today, "count": _count_for(zones, zone, today) + 1}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".alert_daily_count_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"zones": zones}))
        os.replace(tmp_name, path)
    except OSError:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
