"""
Python mirror of internal/model/naismith.go — Issue #802, #3196.

Compute-on-Save: berechnet arrival_calculated für jeden Wegpunkt einer Etappe.
Issue #3196: Gehzeit nach DAV (DIN 33466) statt Naismith-Summe, Tempo aus dem
Trip-Feld ``tempo`` (Fortbewegung + Grundtempo). Bit-genau zu Go — gleiche
Falltabelle (tests/fixtures/naismith_dav_paritaet.json), gleiche Ergebnisse.
"""
from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Any, Tuple, Union

from utils.geo import haversine_km

if TYPE_CHECKING:
    from app.trip import Stage

_DEFAULT_START = "08:00"

Speeds = Tuple[float, float, float]

# Issue #3196: Referenzwerte je Fortbewegung (Vorschlags-Grundtempo km/h,
# Aufstiegs-/Abstiegsrate Hm/h bei genau diesem Tempo). Spiegelt Go
# model.FortbewegungRef (EINE Quelle dort) und TS FORTBEWEGUNG_REF.
_REFERENZ = {
    "fuss": (4.0, 300.0, 500.0),
    "rad": (20.0, 600.0, 1000.0),
    "mtb": (12.0, 500.0, 1000.0),
    "ski": (3.0, 300.0, 1500.0),
}
# Grenzen eines plausiblen Grundtempos (wie Go Min/MaxGrundtempoKmh). Die
# Untergrenze verhindert OverflowError bei winzigen Altwerten (Fix-Loop 2, F001).
_MIN_GRUNDTEMPO_KMH = 0.5
_MAX_GRUNDTEMPO_KMH = 60.0
_RAD_ALTWERTE = {"fahrrad_15": 15, "fahrrad_20": 20, "fahrrad_25": 25}


def derive_tempo(activity: "str | None") -> dict:
    """Leitet ``tempo`` aus dem Altfeld ``activity`` ab (Lazy-Migration).

    fahrrad_15/20/25 → rad mit 15/20/25 km/h, alles andere → fuss 4 km/h.
    Nie mtb oder ski (Spec #3196, AC-2). Spiegelt Go DeriveTempo.
    """
    kmh = _RAD_ALTWERTE.get(activity or "")
    if kmh is not None:
        return {"fortbewegung": "rad", "grundtempo_kmh": kmh}
    return {"fortbewegung": "fuss", "grundtempo_kmh": 4}


def valid_tempo(tempo: Any) -> bool:
    """Bekannte Fortbewegung und 0.5 <= Grundtempo <= 60 km/h (wie Go ValidTempo)."""
    if not isinstance(tempo, dict) or tempo.get("fortbewegung") not in _REFERENZ:
        return False
    v = tempo.get("grundtempo_kmh")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return _MIN_GRUNDTEMPO_KMH <= v <= _MAX_GRUNDTEMPO_KMH


def speeds_for_tempo(tempo: Any) -> Speeds:
    """(flat_kmh, ascent_mh, descent_mh) aus einem Tempo: R = R_ref · v / v_ref.

    Ungültiges Tempo → zu Fuß mit Vorschlagswert (wie Go TempoSpeeds).
    """
    if not valid_tempo(tempo):
        tempo = {"fortbewegung": "fuss", "grundtempo_kmh": 4}
    v_ref, r_auf, r_ab = _REFERENZ[tempo["fortbewegung"]]
    v = float(tempo["grundtempo_kmh"])
    f = v / v_ref
    return (v, r_auf * f, r_ab * f)


def tempo_speeds(trip: Any) -> Speeds:
    """Einzige Auflösungsstelle des Trip-Tempos (Spiegel Go ResolveTempo).

    Gespeichertes ``trip.tempo`` vor Ableitung aus dem Altfeld ``activity``.
    """
    tempo = getattr(trip, "tempo", None)
    if tempo is None:
        tempo = derive_tempo(getattr(trip, "activity", "") or "")
    return speeds_for_tempo(tempo)


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


def dav_hours(dist_km: float, asc_m: float, desc_m: float, sp: Speeds) -> float:
    """Gehzeit nach DAV (DIN 33466), Spiegel Go DAVHours (Issue #3196).

    t_h = km / v, t_v = Hm_auf/R_auf + Hm_ab/R_ab, t = max + min / 2.
    """
    t_h = dist_km / sp[0]
    t_v = asc_m / sp[1] + desc_m / sp[2]
    return max(t_h, t_v) + min(t_h, t_v) / 2


def compute_stage_arrivals(stage: "Stage", tempo: "Union[Speeds, str]") -> "Stage":
    """Berechnet arrival_calculated für jeden Wegpunkt — funktional, neue Stage.

    Stage und Waypoint sind frozen=True → dataclasses.replace für neue Objekte.
    Spiegelt Go ComputeStageArrivals bit-genau.

    ``tempo``: Tempoparameter aus ``tempo_speeds(trip)``. Ein String wird als
    Altwert ``activity`` gelesen und über ``derive_tempo`` abgeleitet.

    - 0 Wegpunkte: Stage unverändert zurück.
    - start_time: datetime.time → "HH:MM"; None → Default "08:00".
    - wp[0].arrival_calculated = formatHHMM(round(start_minutes)).
    - wp[i].arrival_calculated = kumulativer Zeitfortschritt nach DAV je
      Wegpunkt-Paar.
    """
    if not stage.waypoints:
        return stage

    if isinstance(tempo, str):
        sp = speeds_for_tempo(derive_tempo(tempo))
    else:
        sp = tempo

    # stage.start_time ist ein datetime.time oder None
    if stage.start_time is not None:
        start_str = stage.start_time.strftime("%H:%M")
    else:
        start_str = None

    # Issue #2082: EINE Regel fuer "ist diese Etappe vermessen" -- die
    # kanonische aus `stage_measured_distances` (strikte Monotonie UND
    # Plausibilitaet gegen die Luftlinie, je Etappe alles-oder-nichts).
    # Import in der Funktion: `core` soll nicht beim Laden an `services`
    # haengen (Muster wie in `services/track_resolution.py`).
    from services.trip_segments import stage_measured_distances

    measured = stage_measured_distances(stage.waypoints)

    cur = float(_parse_start_minutes(start_str))
    new_waypoints = []

    for i, wp in enumerate(stage.waypoints):
        if i == 0:
            new_wp = dataclasses.replace(wp, arrival_calculated=_format_hhmm(_round(cur)))
            new_waypoints.append(new_wp)
        else:
            prev = stage.waypoints[i - 1]
            if measured is not None:
                dist = measured[i] - measured[i - 1]
            else:
                dist = haversine_km(prev.lat, prev.lon, wp.lat, wp.lon)
            d_elev = float((wp.elevation_m or 0) - (prev.elevation_m or 0))
            asc = max(0.0, d_elev)
            desc = max(0.0, -d_elev)
            cur += dav_hours(dist, asc, desc, sp) * 60.0
            new_wp = dataclasses.replace(wp, arrival_calculated=_format_hhmm(_round(cur)))
            new_waypoints.append(new_wp)

    return dataclasses.replace(stage, waypoints=new_waypoints)
