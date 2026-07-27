"""
Timezone utilities for local time display.

Converts UTC datetimes to local timezone for user-facing output.
Internal pipeline stays 100% UTC — conversion happens only at render time.

SPEC: docs/specs/bugfix/utc_localtime_display.md
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")

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


def resolve_location_tz(location) -> Optional[ZoneInfo]:
    """Ort → Zeitzone. EINZIGER Aufloeser fuer Trip- UND Vergleichs-Pfad
    (Issue #1378, PO-Entscheidung E3) — kein zweiter Weg, keine lokale Kopie.

    Vorrang: gespeichertes ``timezone``-Feld (``SavedLocation.timezone``),
    sonst ``tz_for_coords(lat, lon)``. ``None`` heisst "nicht aufloesbar":
    kein Feld gesetzt, keine Koordinaten oder TimezoneFinder findet nichts.
    Der Aufrufer entscheidet dann bewusst (Mail: sichtbar als UTC markieren,
    s. ``location_tz``; SMS: ``@Stunde`` entfaellt ersatzlos, 140-Zeichen-
    Budget). Ein Ort, dessen Koordinaten auf UTC selbst zeigen, gilt hier als
    nicht aufloesbar — die Anzeige ist in beiden Faellen identisch (UTC),
    nur eben ehrlich als Serverzeit gekennzeichnet.
    """
    name = getattr(location, "timezone", None)
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    lat = getattr(location, "lat", getattr(location, "latitude", None))
    lon = getattr(location, "lon", getattr(location, "longitude", None))
    if lat is None or lon is None:
        return None
    tz = tz_for_coords(lat, lon)
    return None if str(tz) == "UTC" else tz


def location_tz(location) -> ZoneInfo:
    """``resolve_location_tz()`` mit UTC-Rueckfall — fuer die Anzeige-Pfade,
    die immer eine Zeitzone brauchen (Stundenauswahl, Beschriftung, Ausblick,
    Kopfzeile). Der Rueckfall bleibt durch ``local_stamp()`` sichtbar."""
    return resolve_location_tz(location) or UTC


def _as_utc(dt: datetime) -> datetime:
    """Naive Zeitstempel sind per Hausnorm (#1345) UTC. Explizit machen, statt
    ``astimezone()`` die PROZESS-Zeitzone raten zu lassen — sonst haengt das
    Ergebnis am TZ der Maschine statt an den Daten."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def local_dt(dt: datetime, tz: ZoneInfo) -> datetime:
    """UTC datetime → aware datetime in local timezone."""
    return _as_utc(dt).astimezone(tz)


def local_hour(dt: datetime, tz: ZoneInfo) -> int:
    """UTC datetime → local hour."""
    return local_dt(dt, tz).hour


def local_fmt(dt: datetime, tz: ZoneInfo, fmt: str = "%H:%M") -> str:
    """UTC datetime → formatted string in local timezone."""
    return local_dt(dt, tz).strftime(fmt)


def tz_abbrev(dt: datetime, tz: ZoneInfo) -> str:
    """Erkennbares Zeitzonen-Kuerzel zum Zeitpunkt ``dt`` (``CEST``/``CET``/
    ``MDT``/``UTC``). Zeitpunkt-abhaengig, weil dasselbe Gebiet im Sommer ein
    anderes Kuerzel traegt als im Winter — deshalb IMMER mit dem Zeitpunkt
    aufrufen, den die angeschriebene Stelle auch zeigt."""
    return local_dt(dt, tz).strftime("%Z") or "UTC"


def local_stamp(dt: datetime, tz: ZoneInfo, fmt: str = "%H:%M") -> str:
    """Ortszeit MIT erkennbarem Zeitzonen-Kuerzel, z.B. ``06:58 (CEST)`` bzw.
    ``04:58 (UTC)`` — eine Formatier-Quelle fuer HTML- und Klartext-Kopfzeile
    (Issue #1378 AC-4/AC-7/AC-8). Der UTC-Rueckfall bleibt dadurch sichtbar,
    statt wie eine Ortszeit auszusehen."""
    return f"{local_fmt(dt, tz, fmt)} ({tz_abbrev(dt, tz)})"
