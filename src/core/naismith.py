"""
Python mirror of internal/model/naismith.go — Issue #802.

Compute-on-Save: berechnet arrival_calculated für jeden Wegpunkt einer Etappe
nach Naismith's Rule (SUMME, nicht MAX). Bit-genau zu Go — gleiche Fixtures,
gleiche Ergebnisse.
"""
from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Tuple

from utils.geo import haversine_km

if TYPE_CHECKING:
    from app.trip import Stage, Waypoint

_DEFAULT_START = "08:00"


def activity_speeds(activity: str) -> Tuple[float, float, float]:
    """Liefert (flat_kmh, ascent_mh, descent_mh) für eine Aktivität.

    Spiegelt Go ActivitySpeed() — Wanderer-Default und Fahrrad-Stufen identisch.
    """
    if activity == "fahrrad_15":
        return (15.0, 600.0, 1000.0)
    if activity == "fahrrad_20":
        return (20.0, 600.0, 1000.0)
    if activity == "fahrrad_25":
        return (25.0, 600.0, 1000.0)
    return (4.0, 300.0, 500.0)


def _parse_start_minutes(start_time: "str | None") -> int:
    """Parst "HH:MM" in Minuten ab Mitternacht. Ungültig oder None → 480 (08:00).

    Spiegelt Go parseStartMinutes: h>23 oder m>59 → Default.
    """
    s = start_time if start_time else _DEFAULT_START
    try:
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if h < 0 or h > 23 or m < 0 or m > 59:
            raise ValueError
        return h * 60 + m
    except (ValueError, AttributeError):
        return 8 * 60


def _format_hhmm(total_min: int) -> str:
    """Formatiert Minuten ab Mitternacht als "HH:MM", Wrap ueber Mitternacht.

    Spiegelt Go formatHHMM.

    Issue #1667 S2: bis dahin wurde auf 23:59 geklemmt. Der Grund dafuer bleibt
    gueltig — `_parse_hhmm` (und die Go-/TS-Gegenseiten) koennen einen
    Stunden-Teil >23 nicht konsumieren und fielen sonst still auf die divergente
    Interpolation zurueck. Der Modulo ERFUELLT diese Bedingung, statt sie zu
    umgehen: die Ausgabe bleibt im Bereich 00:00-23:59. Er behebt zugleich den
    Defekt der Klemme — mehrere Wegpunkte fielen auf denselben Wert "23:59",
    wodurch der wp_days-Rollover in trip_segments.py den Tageswechsel nicht
    mehr erkannte und Segmente samt Wetterueberwachung verworfen wurden.

    Kein negativsicherer Modulo (((x % m) + m) % m) noetig: total_min ist
    konstruktiv >= 0 (Startzeit >= 0 plus kumulierte, nie negative
    Naismith-Minuten). Bitte nicht "sicherheitshalber" umbauen.
    """
    total_min = total_min % (24 * 60)
    return f"{total_min // 60:02d}:{total_min % 60:02d}"


def _round(x: float) -> int:
    """Round-half-away-from-zero (wie Go math.Round), NICHT Python-Banker-round."""
    return math.floor(x + 0.5)


def _naismith_hours(
    dist_km: float, asc_m: float, desc_m: float, sp: Tuple[float, float, float]
) -> float:
    """Naismith als SUMME (nicht MAX). Spiegelt Go naismithHours."""
    return dist_km / sp[0] + asc_m / sp[1] + desc_m / sp[2]


def _segment_distance_km(prev: "Waypoint", wp: "Waypoint") -> float:
    """Wegstrecke zwischen zwei Wegpunkten in km — Issue #2042.

    Tragen BEIDE Wegpunkte eine gemessene Strecke (`distance_from_start_km`,
    seit #2036), ist deren Differenz die tatsaechlich zu gehende Strecke.
    Sonst bleibt es bei der Luftlinie wie im Bestand.

    Die Entscheidung faellt je Wegpunktpaar, nicht je Etappe: eine teilweise
    vermessene Etappe rechnet die vermessenen Abschnitte gemessen.

    Eine negative Differenz kann es bei korrekten Daten nicht geben; sie wuerde
    die Gehzeit verkuerzen und damit genau den Fehler erzeugen, den #2042
    behebt. Deshalb faellt auch dieser Fall auf die Luftlinie zurueck.

    Spiegelt Go segmentDistanceKm.
    """
    prev_km = getattr(prev, "distance_from_start_km", None)
    wp_km = getattr(wp, "distance_from_start_km", None)
    if prev_km is not None and wp_km is not None:
        delta = float(wp_km) - float(prev_km)
        if delta >= 0.0:
            return delta
    return haversine_km(prev.lat, prev.lon, wp.lat, wp.lon)


def compute_stage_arrivals(stage: "Stage", activity: str) -> "Stage":
    """Berechnet arrival_calculated für jeden Wegpunkt — funktional, neue Stage.

    Stage und Waypoint sind frozen=True → dataclasses.replace für neue Objekte.
    Spiegelt Go ComputeStageArrivals bit-genau.

    - 0 Wegpunkte: Stage unverändert zurück.
    - start_time: datetime.time → "HH:MM"; None → Default "08:00".
    - wp[0].arrival_calculated = formatHHMM(round(start_minutes)).
    - wp[i].arrival_calculated = kumulativer Zeitfortschritt via Naismith.
    """
    if not stage.waypoints:
        return stage

    sp = activity_speeds(activity)

    # stage.start_time ist ein datetime.time oder None
    if stage.start_time is not None:
        start_str = stage.start_time.strftime("%H:%M")
    else:
        start_str = None

    cur = float(_parse_start_minutes(start_str))
    new_waypoints = []

    for i, wp in enumerate(stage.waypoints):
        if i == 0:
            new_wp = dataclasses.replace(wp, arrival_calculated=_format_hhmm(_round(cur)))
            new_waypoints.append(new_wp)
        else:
            prev = stage.waypoints[i - 1]
            dist = _segment_distance_km(prev, wp)
            d_elev = float((wp.elevation_m or 0) - (prev.elevation_m or 0))
            asc = max(0.0, d_elev)
            desc = max(0.0, -d_elev)
            cur += _naismith_hours(dist, asc, desc, sp) * 60.0
            new_wp = dataclasses.replace(wp, arrival_calculated=_format_hhmm(_round(cur)))
            new_waypoints.append(new_wp)

    return dataclasses.replace(stage, waypoints=new_waypoints)
