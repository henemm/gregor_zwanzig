"""Ortstag-Helfer fuer Test-Fixtures (Issue #2314).

Das Produkt rechnet den Kalendertag in der Ortszone der Trip-Koordinaten
(`trip_local_today`, ADR-0044). Fixtures, die Etappen/Anker mit
`date.today()` (Prozesstag) datieren, laufen deshalb nachts gegen den
falschen Tag. Dieser Helfer liefert den Tag, den das Produkt meint.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from utils.timezone import tz_for_coords


def ortstag(lat: float, lon: float, *, now_utc: datetime | None = None) -> date:
    """Der Kalendertag am Ort (lat, lon), gemessen an now_utc (Default: jetzt).

    lat/lon sind PFLICHT ohne Default — ein stiller Rueckfall auf Prozess-
    oder Test-Standardkoordinaten wuerde genau den Fehler reproduzieren,
    den dieser Helfer behebt. Reine Delegation an das produktive
    tz_for_coords(); keine eigene Zonenarithmetik. Die Uhr wird zur
    Aufrufzeit gelesen (freezegun-kompatibel).
    """
    jetzt = now_utc if now_utc is not None else datetime.now(timezone.utc)
    return jetzt.astimezone(tz_for_coords(lat, lon)).date()


def etappe_am_ortstag(lat: float, lon: float, *, stage_id: str = "T1") -> dict:
    """Trip-Etappe (JSON-Form) am Ortstag mit zwei Wegpunkten = genau ein
    echtes Segment ``"1"`` (Issue #2069: die Alarm-Vorschau akzeptiert nur
    Segment-Kennungen, die der Trip am Bezugstag wirklich hat)."""
    return {
        "id": stage_id, "name": "Etappe 1", "date": ortstag(lat, lon).isoformat(),
        "waypoints": [
            {"id": "G1", "name": "Start", "lat": lat, "lon": lon,
             "elevation_m": 1000, "arrival_override": "08:00"},
            {"id": "G2", "name": "Ziel", "lat": lat + 0.05, "lon": lon + 0.05,
             "elevation_m": 1400, "arrival_override": "10:00"},
        ],
    }


def utc_tag(*, now_utc: datetime | None = None) -> date:
    """Der UTC-Kalendertag, gemessen an now_utc (Default: jetzt).

    Fuer Fixtures, die einen Zaehler oder Cache-Eintrag datieren, den das
    Produkt am UTC-Tag verankert (_today_utc, FixtureProvider). Keine eigene
    Zonenarithmetik -- reiner .date()-Zugriff auf einen UTC-Zeitpunkt.
    """
    jetzt = now_utc if now_utc is not None else datetime.now(timezone.utc)
    return jetzt.date()
